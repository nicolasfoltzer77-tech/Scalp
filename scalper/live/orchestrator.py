# scalper/live/orchestrator.py
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from scalper.services.utils import safe_call, heartbeat_task, log_stats_task
from scalper.live.notify import build_notifier_and_commands  # crée Notifier + CommandStream

# ------------------------------------------------------------------------------
# Fabrique de signaux (plugin) — garde simple : current par défaut
# ------------------------------------------------------------------------------
def load_signal(name: str):
    # Lazy import pour éviter les cycles
    from importlib import import_module
    try:
        mod = import_module(f"scalper.signals.{name}")
        return getattr(mod, "generate_signal")
    except Exception:
        # Fallback très simple
        def _noop(symbol: str, ohlcv: list[list[float]], cash: float, risk_pct: float) -> dict:
            return {"action": "hold"}
        return _noop


class Orchestrator:
    """
    Orchestrateur live :
    - PRELAUNCH : heartbeat + stats + commandes Telegram (si dispo)
    - RUNNING   : crée une tâche par symbole (boucle OHLCV -> signal -> logs/exec)
    """

    def __init__(self, exchange: Any, config: Dict[str, Any]):
        self.exchange = exchange
        self.config = dict(config)

        self.symbols: List[str] = list(self.config.get("symbols") or [])
        self.timeframe: str = str(self.config.get("timeframe") or "5m")

        # stratégie (factory commune live/backtest)
        self.selected = {
            "strategy": str(self.config.get("strategy") or "current"),
        }
        self.generate_signal = load_signal(self.selected["strategy"])

        # état
        self._state: str = "PRELAUNCH"
        self.ticks_total: int = 0

        # Notifier & commandes
        self.notifier = None
        self.command_stream = None  # itérable async des commandes

        # tâches de fond
        self._bg_tasks: List[asyncio.Task] = []
        self._loops: List[asyncio.Task] = []

    # -------------------------- propriétés utils -----------------------------
    def running(self) -> bool:
        return self._state == "RUNNING"

    def _stats_snapshot(self) -> Dict[str, Any]:
        return {
            "state": self._state,
            "timeframe": self.timeframe,
            "symbols": list(self.symbols),
        }

    # -------------------------- API publique ---------------------------------
    async def run(self) -> None:
        await self.start()           # PRELAUNCH
        await self._prelaunch_loop() # attend /resume (ou run direct si config)

    async def start(self) -> None:
        # Notifier/commandes (Null si Telegram indispo)
        self.notifier, self.command_stream = await build_notifier_and_commands(self.config)

        await self.notifier.send("🟢 Orchestrator PRELAUNCH.\nUtilise /setup ou /backtest. /resume pour démarrer le live.")

        # tâches heartbeat & stats
        self._bg_tasks.append(asyncio.create_task(
            heartbeat_task(lambda: self._state != "STOPPED", self.notifier, interval=30.0, name="orchestrator")
        ))
        self._bg_tasks.append(asyncio.create_task(
            log_stats_task(
                lambda: self.ticks_total,
                lambda: self.symbols,
                self._stats_snapshot,
                interval=30.0,
            )
        ))

        # démarrage direct si demandé
        if str(self.config.get("autostart", "0")).lower() in ("1", "true", "yes"):
            await self._resume_live()

    async def stop(self) -> None:
        await self._set_state("STOPPED")
        await self.notifier.send("🛑 Orchestrator stopped.")
        # cancel tâches
        for t in self._loops + self._bg_tasks:
            if not t.done():
                t.cancel()
        self._loops.clear()
        self._bg_tasks.clear()

    # -------------------------- Boucle PRELAUNCH -----------------------------
    async def _prelaunch_loop(self) -> None:
        """
        Boucle d'attente : /resume pour lancer le live, /stop pour quitter,
        /backtest & /setup sont relayés par le Notifier/CommandStream si disponible.
        """
        try:
            while self._state != "STOPPED":
                cmd = None
                if self.command_stream is not None:
                    try:
                        cmd = await asyncio.wait_for(self.command_stream.get(), timeout=1.0)
                    except asyncio.TimeoutError:
                        cmd = None

                if not cmd:
                    await asyncio.sleep(0.2)
                    continue

                # Parsing très simple
                cmd = str(cmd).strip().lower()
                if cmd == "/resume":
                    await self._resume_live()
                elif cmd == "/stop":
                    await self.stop()
                    break
                elif cmd in ("/status",):
                    await self._send_status()
                else:
                    # d'autres commandes (/setup, /backtest) sont gérées dans notify
                    pass
        finally:
            # propre quand on sort
            for t in self._bg_tasks:
                if not t.done():
                    t.cancel()
            self._bg_tasks.clear()

    async def _send_status(self) -> None:
        pairs = ", ".join(self.symbols) or "-"
        await self.notifier.send(f"ℹ️ state={self._state} | tf={self.timeframe} | pairs={pairs} | ticks={self.ticks_total}")

    async def _resume_live(self) -> None:
        if self.running():
            await self.notifier.send("⚠️ Live déjà démarré.")
            return
        await self._set_state("RUNNING")
        await self.notifier.send("▶️ Live démarré.")

        # Crée une tâche par symbole
        self._loops = [
            asyncio.create_task(self._symbol_loop(sym))
            for sym in self.symbols
        ]

    async def _set_state(self, new_state: str) -> None:
        self._state = new_state

    # -------------------------- Boucle par symbole ---------------------------
    async def _symbol_loop(self, symbol: str) -> None:
        """
        Boucle : fetch OHLCV -> generate_signal -> (logs/exec hook à compléter)
        Tous les IO passent via safe_call.
        """
        tf = self.timeframe
        while self.running():
            try:
                ohlcv = await safe_call(self.exchange.fetch_ohlcv, f"{symbol}", symbol, tf, limit=200)
                # incrément ticks
                self.ticks_total += 1

                # stratégie
                sig = self.generate_signal(
                    symbol,
                    ohlcv,
                    float(self.config.get("cash", 10_000.0)),
                    float(self.config.get("risk_pct", 0.05)),
                )
                # TODO: brancher logs CSV et exécution d’ordres
                # ex: await self._log_signal(symbol, ohlcv[-1], sig)

            except Exception as e:  # noqa: BLE001
                await self.notifier.send(f"[{symbol}] loop error: {e}")
                await asyncio.sleep(1.0)
                continue

            await asyncio.sleep(0.2)  # tempo court (évite boucle trop serrée)

# ------------------------------------------------------------------------------
# Entrée unique appelée par bot.py
# ------------------------------------------------------------------------------
async def run_orchestrator(exchange: Any, config: Dict[str, Any]) -> None:
    orch = Orchestrator(exchange, config)
    try:
        await orch.run()
    finally:
        try:
            await orch.stop()
        except Exception:
            pass