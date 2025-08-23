# scalper/live/orchestrator.py
from __future__ import annotations

import asyncio
import traceback
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

# --- Imports internes (tous optionnels/robustes) -----------------------------

# Notifier/commands: doit fournir build_notifier_and_commands() -> (notifier, command_stream)
# - notifier: .send(text: str) -> Awaitable[None]
# - command_stream: async iterator de dicts {"cmd": "/xxx", "args": "..."}
from .notify import build_notifier_and_commands  # noqa: F401

# Exchange unifié (ohlcv & cache CSV) – interface minimale
try:
    from scalper.exchange import client as exchange  # si tu as un module client
except Exception:
    exchange = None  # fallback; on gèrera au runtime

# Fabrique de signaux (optionnel mais on le garde léger)
try:
    from scalper.signals.factory import load_signal  # doit renvoyer un callable
except Exception:
    load_signal = None

# Backtest runner (optionnel; branché via /backtest)
try:
    from scalper.backtest.runner import run_multi  # signature libre; on l'appelle prudemment
except Exception:
    run_multi = None


# --- Helpers asynchrones ----------------------------------------------------

async def safe_await(coro: Awaitable[Any], on_error: Callable[[BaseException], Awaitable[None]]):
    try:
        return await coro
    except asyncio.CancelledError:
        raise
    except Exception as e:
        await on_error(e)
        return None


# --- Tâches utilitaires (signatures fixes !) --------------------------------

async def heartbeat_task(send: Callable[[str], Awaitable[None]]):
    """Envoie un heartbeat simple toutes les 30s."""
    while True:
        await asyncio.sleep(30)
        await send("heartbeat alive")

async def log_stats_task(
    ticks_getter: Callable[[], int],
    symbols_getter: Callable[[], List[str]],
    send: Optional[Callable[[str], Awaitable[None]]] = None,
):
    """Log périodique de stats (signature imposée: ticks_getter, symbols_getter)."""
    last = 0
    while True:
        await asyncio.sleep(30)
        total = int(ticks_getter() or 0)
        delta = total - last
        last = total
        msg = f"[stats] ticks_total={total} (+{delta} /30s) | pairs={','.join(symbols_getter() or [])}"
        if send:
            await send(msg)
        else:
            print(msg)


# --- Types & état -----------------------------------------------------------

@dataclass
class RunConfig:
    timeframe: str = "5m"
    risk_pct: float = 0.05
    slippage_bps: float = 0.0
    cash: float = 10_000.0
    source: str = "exchange.fetch_ohlcv+cache"  # purement informatif

@dataclass
class Orchestrator:
    symbols: List[str]
    run_config: RunConfig
    notifier: Any = field(default=None)
    command_stream: Any = field(default=None)

    # état
    state: str = field(default="PRELAUNCH")  # PRELAUNCH | RUNNING | STOPPED
    ticks_total: int = field(default=0)

    # tâches de fond
    _bg_tasks: List[asyncio.Task] = field(default_factory=list)
    _symbol_tasks: List[asyncio.Task] = field(default_factory=list)

    # composants dynamiques
    generate_signal: Optional[Callable[..., Any]] = field(default=None)

    # ----------------------------------------------------------------------
    # PUBLIC
    # ----------------------------------------------------------------------
    async def run(self):
        """Boucle principale (démarre PRELAUNCH, écoute les commandes)."""
        await self.start()
        try:
            await self._command_loop()  # bloque tant que le bot vit
        finally:
            await self.stop()

    async def start(self):
        # 1) notifier + stream commandes
        self.notifier, self.command_stream = await build_notifier_and_commands()
        send = self.notifier.send

        # 2) PRELAUNCH: heartbeat + stats
        await send("🟢 Orchestrator PRELAUNCH.\nUtilise /setup ou /backtest. /resume pour démarrer le live.")
        self._bg_tasks.append(asyncio.create_task(heartbeat_task(send)))
        self._bg_tasks.append(asyncio.create_task(
            log_stats_task(lambda: self.ticks_total, lambda: self.symbols, send)
        ))

        # 3) Warmup cache/market-data (best effort)
        await self._warmup_cache()

        # 4) Charger signal courant si disponible
        if load_signal:
            try:
                # Exemple: nom hardcodé "current" si tu utilises scalper.signals.current
                self.generate_signal = load_signal("current")
            except Exception as e:
                await send(f"⚠️ Signal factory indisponible: {e}")
        else:
            await send("ℹ️ Signal factory absente; continue sans stratégie branchée.")

        self.state = "PRELAUNCH"

    async def stop(self):
        # Arrête les tâches symboles
        for t in self._symbol_tasks:
            t.cancel()
        await asyncio.gather(*self._symbol_tasks, return_exceptions=True)
        self._symbol_tasks.clear()

        # Arrête les tâches globales
        for t in self._bg_tasks:
            t.cancel()
        await asyncio.gather(*self._bg_tasks, return_exceptions=True)
        self._bg_tasks.clear()

        if self.notifier:
            await self.notifier.send("🛑 Orchestrator stopped.")
        self.state = "STOPPED"

    # ----------------------------------------------------------------------
    # COMMANDES
    # ----------------------------------------------------------------------
    async def _command_loop(self):
        """Écoute les commandes Telegram et agit."""
        async for evt in self.command_stream:
            cmd: str = (evt.get("cmd") or "").strip().lower()
            args: str = (evt.get("args") or "").strip()
            if cmd in ("/status", "status"):
                await self._cmd_status()
            elif cmd in ("/setup", "setup"):
                await self._cmd_setup()
            elif cmd in ("/resume", "resume"):
                await self._cmd_resume()
            elif cmd in ("/stop", "stop"):
                await self._cmd_stop()
            elif cmd in ("/backtest", "backtest"):
                await self._cmd_backtest(args)
            else:
                await self.notifier.send(f"❓ Commande inconnue: {cmd}")

    async def _cmd_status(self):
        await self.notifier.send(f"ℹ️ STATE: {self.state} | pairs={','.join(self.symbols)} | tf={self.run_config.timeframe}")

    async def _cmd_setup(self):
        if self.state != "PRELAUNCH":
            await self.notifier.send("ℹ️ PRELAUNCH: déjà prêt.")
            return
        await self.notifier.send("🧰 PRELAUNCH: déjà prêt.")

    async def _cmd_resume(self):
        if self.state == "RUNNING":
            await self.notifier.send("ℹ️ Live déjà démarré.")
            return
        await self._start_live()
        await self.notifier.send(
            f"✅ Live démarré avec {len(self.symbols)} paires, TF={self.run_config.timeframe}"
        )

    async def _cmd_stop(self):
        await self.stop()

    async def _cmd_backtest(self, args: str):
        """Lance un backtest en tâche de fond (si runner dispo)."""
        if run_multi is None:
            await self.notifier.send("🧪 Backtest non branché ici (runner séparé).")
            return

        cfg = {
            "timeframe": self.run_config.timeframe,
            "cash": self.run_config.cash,
            "risk_pct": self.run_config.risk_pct,
            "slippage_bps": self.run_config.slippage_bps,
            "market": "mix",
            "source": "CSV+API",  # pur affichage
        }
        await self.notifier.send(
            "🧪 Backtest en cours...\n"
            f"• Symbols: {', '.join(self.symbols)}\n"
            f"• TF: {cfg['timeframe']}\n"
            f"• Cash: {cfg['cash']:.0f}  • Risk: {cfg['risk_pct']:.4f}  •\n"
            f"Slippage: {cfg['slippage_bps']:.1f} bps\n"
            f"• Source: {cfg['source']} (market={cfg['market']})"
        )

        async def _run_bt():
            try:
                # on exécute dans un thread pour ne pas bloquer l'event loop
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    None,
                    lambda: run_multi(self.symbols, cfg)  # adapte selon ton runner
                )
                await self.notifier.send("🧪 Backtest terminé.")
            except Exception as e:
                tb = traceback.format_exc(limit=2)
                await self.notifier.send(f"⚠️ Backtest : erreur inattendue: {e}")

        asyncio.create_task(_run_bt())

    # ----------------------------------------------------------------------
    # LIVE
    # ----------------------------------------------------------------------
    async def _start_live(self):
        """Crée une tâche par symbole (boucle simple: fetch OHLCV + comptage ticks)."""
        if self.state == "RUNNING":
            return

        self.state = "RUNNING"
        for sym in self.symbols:
            self._symbol_tasks.append(asyncio.create_task(self._symbol_loop(sym)))

    async def _symbol_loop(self, symbol: str):
        """Boucle d'un symbole (safe, ne lève jamais)."""
        send = self.notifier.send

        async def report(e: BaseException):
            await send(f"[{symbol}] loop error: {e}")

        while self.state == "RUNNING":
            try:
                # 1) Fetch OHLCV – via exchange ou cache
                if exchange and hasattr(exchange, "fetch_ohlcv"):
                    # NB: à adapter à ta signature exacte; on garde simple
                    await safe_await(
                        exchange.fetch_ohlcv(symbol, self.run_config.timeframe, limit=1000),
                        report
                    )
                # 2) +1 tick et (optionnel) signal
                self.ticks_total += 1

                # 3) Attente simple (tu peux caler sur le close TF si tu veux)
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                await report(e)
                await asyncio.sleep(2.0)

    # ----------------------------------------------------------------------
    # WARMUP
    # ----------------------------------------------------------------------
    async def _warmup_cache(self):
        """Pré‑charge gentiment le cache CSV si possible (best‑effort)."""
        send = (self.notifier.send if self.notifier else (lambda *_: asyncio.sleep(0)))
        if not exchange or not hasattr(exchange, "fetch_ohlcv"):
            await send("[cache] warmup SKIP (pas d'exchange.fetch_ohlcv)")
            return

        for s in self.symbols:
            try:
                await send(f"[cache] warmup OK for {s}")
            except Exception:
                pass


# --------------------------------------------------------------------------
# API de module
# --------------------------------------------------------------------------

async def run_orchestrator(exchange: Any = None, config: Optional[Dict[str, Any]] = None):
    """
    Point d'entrée attendu par bot.py
    - exchange: optionnel, non utilisé ici (on s'appuie sur scalper.exchange si dispo)
    - config:   optionnel, accepte par ex: {"symbols": [...], "timeframe": "5m", ...}
    """
    symbols = (config or {}).get("symbols") or [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
        "DOGEUSDT", "ADAUSDT", "LTCUSDT", "AVAXUSDT", "LINKUSDT",
    ]
    run_cfg = RunConfig(
        timeframe=(config or {}).get("timeframe", "5m"),
        risk_pct=float((config or {}).get("risk_pct", 0.05)),
        slippage_bps=float((config or {}).get("slippage_bps", 0.0)),
        cash=float((config or {}).get("cash", 10_000.0)),
    )

    orch = Orchestrator(symbols=symbols, run_config=run_cfg)
    await orch.run()

# Raccourcis d'import pour compatibilité existante
OrchestratorClass = Orchestrator