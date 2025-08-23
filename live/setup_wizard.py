from __future__ import annotations
import asyncio, os
from dataclasses import dataclass
from typing import List, Dict, Optional, Callable
from ..signals.factory import load_signal
from ..backtest.runner import BacktestRunner
from .notify import Notifier, CommandStream

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
    Utilise Notifier (send/send_menu) + CommandStream (async iterator).
    """
    def __init__(self, notifier: Notifier, cmd_stream: CommandStream,
                 ohlcv_loader_sync: Callable, out_dir: str = "out_bt_setup",
                 admin_chat_id: Optional[int]=None):
        self.notifier = notifier
        self.cmd_stream = cmd_stream
        self.loader = ohlcv_loader_sync
        self.out_dir = out_dir
        self.admin_chat_id = admin_chat_id

    async def _ask_list(self, prompt: str, choices: List[str], allow_multi=True) -> List[str]:
        await self.notifier.send_menu(prompt, choices)
        async for msg in self.cmd_stream:
            txt = msg.strip()
            if allow_multi and ("," in txt or " " in txt):
                sel = [t.strip() for t in txt.replace(" ", "").split(",") if t.strip()]
                return sel
            if txt.isdigit():
                i = int(txt)-1
                if 0 <= i < len(choices):
                    return [choices[i]]
            if txt in choices:
                return [txt]
            await self.notifier.send("Entrée invalide. Réessaie.")

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

    async def run(self, default_symbols: List[str], default_timeframes: List[str],
                  default_strategy: str="current") -> SetupResult:
        await self.notifier.send("🧪 Validation avant trading : choix strat/symbols/TF → backtest → validation.")
        # 1) stratégie
        strategies = ["current","ema_cross","vwap_break"]
        [strategy] = await self._ask_list("Choisis la stratégie :", strategies, allow_multi=False)

        # 2) symboles
        symbols = await self._ask_list("Sélectionne les symboles :", default_symbols, allow_multi=True)

        # 3) timeframes
        timeframes = await self._ask_list("Sélectionne les timeframes :", default_timeframes, allow_multi=True)

        # 4) risk %
        risk_pct = await self._ask_value("Risk % du solde (ex: 0.5 = 50%)", float, 0.5)

        # 5) période backtest
        start = await self._ask_value("Date de début (YYYY-MM-DD)", str, "2024-01-01")
        end   = await self._ask_value("Date de fin   (YYYY-MM-DD)", str, "2025-08-01")

        # 6) run backtest
        from ..backtest.cli import parse_ts
        start_ms, end_ms = parse_ts(start), parse_ts(end)
        runner = BacktestRunner(self.loader, self.out_dir, strategy,
                                cfg={}, cash=10_000.0, risk_pct=risk_pct, max_conc=6)
        res = await runner.run_all(symbols, timeframes, start_ms, end_ms)

        # 7) résumé
        sum_path = os.path.join(self.out_dir, "metrics.json")
        prop = res["proposal"]
        lines = ["**Proposition** :"]
        for sym, best in prop["per_symbol_best"].items():
            lines.append(f"• {sym}: {best['timeframe']}  score={best['score']:.3f}  PF={best['pf']:.2f}  WR={best['winrate']:.1%}  DD={best['maxdd']:.1%}")
        await self.notifier.send("\n".join(lines) + f"\nFichier: {sum_path}\n✅ Tape **ACCEPTER** pour lancer\n🔁 **MODIFIER** pour relancer\n❌ **ANNULER** pour quitter.")

        # 8) décision
        async for msg in self.cmd_stream:
            t = msg.strip().lower()
            if t in ("accepter","accept","ok","go","start"):
                await self.notifier.send("✅ Validation reçue — passage en RUNNING.")
                return SetupResult(strategy, symbols, timeframes, risk_pct, True, sum_path)
            if t in ("modifier","again","repeat"):
                return await self.run(default_symbols, default_timeframes, default_strategy=strategy)
            if t in ("annuler","cancel","stop"):
                await self.notifier.send("❌ Annulé.")
                return SetupResult(strategy, symbols, timeframes, risk_pct, False, sum_path)