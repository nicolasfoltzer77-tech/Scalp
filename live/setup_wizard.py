from __future__ import annotations
import asyncio, json, os, time
from dataclasses import dataclass
from typing import List, Dict, Optional, Callable
from ..signals.factory import load_signal
from ..backtest.runner import BacktestRunner

@dataclass
class SetupResult:
    strategy: str
    symbols: List[str]
    timeframes: List[str]
    risk_pct: float
    accepted: bool
    summary_path: str

class SetupWizard:
    """
    Wizard interactif Telegram avant lancement des trades.
    Il utilise Notifier (send/send_menu) + CommandStream (async iterator de messages texte).
    """
    def __init__(self, notifier, cmd_stream, ohlcv_loader_sync: Callable, out_dir: str = "out_bt_setup", admin_chat_id: Optional[int]=None):
        self.notifier = notifier
        self.cmd_stream = cmd_stream
        self.loader = ohlcv_loader_sync
        self.out_dir = out_dir
        self.admin_chat_id = admin_chat_id

    async def _ask_list(self, prompt: str, choices: List[str], allow_multi=True) -> List[str]:
        await self.notifier.send_menu(prompt, choices)
        async for msg in self.cmd_stream:
            txt = msg.strip()
            # Filtrage chat_id si dispo sur ta CommandStream (sinon supprime ce block)
            if hasattr(msg, "chat_id") and self.admin_chat_id and msg.chat_id != self.admin_chat_id:
                continue
            if allow_multi and ("," in txt or " " in txt):
                sel = [t.strip() for t in txt.replace(" ", "").split(",") if t.strip()]
                if all((t in choices) or t.isalnum() for t in sel):
                    return sel
            if txt.isdigit():
                i = int(txt)-1
                if 0 <= i < len(choices):
                    return [choices[i]]
            if txt in choices:
                return [txt]
            await self.notifier.send("Entrée invalide. Réessaie (numéro, valeur ou liste séparée par des virgules).")

    async def _ask_value(self, prompt: str, cast: Callable, default):
        await self.notifier.send(f"{prompt} (défaut: {default})")
        async for msg in self.cmd_stream:
            txt = msg.strip()
            if txt == "" or txt.lower() in ("d","defaut","default"):
                return default
            try:
                return cast(txt)
            except Exception:
                await self.notifier.send("Entrée invalide. Réessaie.")

    async def run(self, default_symbols: List[str], default_timeframes: List[str], default_strategy: str="current") -> SetupResult:
        await self.notifier.send("🧪 **Mode validation avant trading** — on va choisir la stratégie, les paires, les timeframes, lancer un backtest multi‑combos, puis décider.")
        # 1) stratégie
        strategies = ["current", "ema_cross", "vwap_break"]
        if default_strategy not in strategies: strategies.insert(0, default_strategy)
        [strategy] = await self._ask_list("Choisis la stratégie :", strategies, allow_multi=False)

        # 2) symboles
        symbols = await self._ask_list(f"Sélectionne les symboles (liste ou numéro) :", default_symbols, allow_multi=True)

        # 3) timeframes
        timeframes = await self._ask_list("Sélectionne les timeframes :", default_timeframes, allow_multi=True)

        # 4) risk %
        risk_pct = await self._ask_value("Choisis le risk % du solde par position (ex: 0.5 = 50%)", float, 0.5)

        # 5) période backtest
        start = await self._ask_value("Date de début (YYYY-MM-DD)", str, "2024-01-01")
        end   = await self._ask_value("Date de fin   (YYYY-MM-DD)", str, "2025-08-01")

        # 6) run backtest
        await self.notifier.send(f"⏳ Backtest en cours… stratégie={strategy}, {len(symbols)} symboles × {len(timeframes)} TF…")
        from .cli import parse_ts  # réutilise util de la CLI que je t’ai fournie
        start_ms, end_ms = parse_ts(start), parse_ts(end)
        runner = BacktestRunner(self.loader, self.out_dir, strategy, cfg={}, cash=10_000.0, risk_pct=risk_pct, max_conc=6)
        res = await runner.run_all(symbols, timeframes, start_ms, end_ms)

        # 7) résumé + proposition
        sum_path = os.path.join(self.out_dir, "metrics.json")
        prop = res["proposal"]
        lines = ["\n**Proposition** :"]
        for sym, best in prop["per_symbol_best"].items():
            lines.append(f"• {sym}: {best['timeframe']}  score={best['score']:.3f}  PF={best['pf']:.2f}  WR={best['winrate']:.1%}  MaxDD={best['maxdd']:.1%}")
        await self.notifier.send("\n".join(lines) + f"\nFichier détaillé: {sum_path}\n\n✅ Tape **ACCEPTER** pour lancer le trading avec ces réglages,\n🔁 **MODIFIER** pour relancer le wizard,\n❌ **ANNULER** pour quitter.")

        # 8) attente décision
        async for msg in self.cmd_stream:
            t = msg.strip().lower()
            if t in ("accepter", "accept", "ok", "go", "start"):
                await self.notifier.send("✅ Validation reçue — passage en RUNNING.")
                return SetupResult(strategy, symbols, timeframes, risk_pct, True, sum_path)
            if t in ("modifier","again","repeat","recommencer"):
                await self.notifier.send("🔁 On recommence le wizard.")
                return await self.run(default_symbols, default_timeframes, default_strategy=strategy)
            if t in ("annuler","cancel","stop"):
                await self.notifier.send("❌ Annulé. Le bot reste en PRELAUNCH (pas de trade).")
                return SetupResult(strategy, symbols, timeframes, risk_pct, False, sum_path)