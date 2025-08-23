# scalper/live/orchestrator.py
from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Callable, Dict, Iterable, List, Optional

# Utilitaires communs
from scalper.services.utils import safe_call, heartbeat_task, log_stats_task

# Notifier & commandes Telegram (fallback automatique si KO)
from scalper.live.notify import (
    Notifier,
    CommandStream,
    build_notifier_and_commands,
)

# Backtest côté Telegram (pour /backtest)
try:
    from scalper.live.backtest_telegram import handle_backtest_command
except Exception:
    async def handle_backtest_command(notifier: Notifier, symbols: List[str], timeframe: str = "5m"):
        await notifier.send("⚠️ Backtest indisponible dans cette build.")

# ---------------------------------------------------------------------------

def _env_bool(name: str, default: str = "0") -> bool:
    return (os.getenv(name, default) or "").strip().lower() not in ("0", "false", "no", "")

QUIET = _env_bool("QUIET", "1")  # réduit le bruit par défaut

# ---------------------------------------------------------------------------

class Orchestrator:
    """
    Orchestrateur live :
      - création notifier + flux de commandes (Telegram ou Null)
      - boucles par symbole : fetch OHLCV -> génération signal -> logs
      - tâches de fond : heartbeat + stats périodiques
    """

    def __init__(
        self,
        exchange: Any,
        config: Dict[str, Any],
        symbols: Iterable[str],
        timeframe: str = "5m",
    ):
        self.exchange = exchange
        self.config = config
        self.timeframe = timeframe
        self.symbols: List[str] = list(symbols)

        # état
        self._state = "PRELAUNCH"  # PRELAUNCH|RUNNING|PAUSED|STOPPED
        self._closing = False

        # comptage/metrics
        self.ticks_total = 0

        # notifier/commandes
        self.notifier: Notifier
        self.command_stream: Optional[CommandStream] = None

        # tâches de fond
        self._bg_tasks: List[asyncio.Task] = []
        self._symbol_tasks: List[asyncio.Task] = []

    # ------------- helpers état -------------
    def is_running(self) -> bool:
        return self._state == "RUNNING" and not self._closing

    # ------------- IO wrappers -------------
    async def ohlcv_fetch(self, symbol: str, timeframe: str, limit: int = 200):
        async def _call():
            return await self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        return await safe_call(_call, label=f"ohlcv:{symbol}", max_retry=5, base_delay=0.4)

    # ------------- core loops -------------
    async def _symbol_loop(self, symbol: str):
        """Boucle par symbole: fetch ohlcv -> (générer signal) -> (passer ordre/logs)."""
        # NB: remplace generate_signal(...)/order_executor(...) par tes fonctions si disponibles
        default_cash = float(self.config.get("cash", 10_000.0))
        risk_pct = float(self.config.get("risk_pct", 0.05))

        while not self._closing:
            if not self.is_running():
                await asyncio.sleep(0.5)
                continue

            try:
                ohlcv = await self.ohlcv_fetch(symbol, self.timeframe, limit=200)
                # --- placeholder stratégie ---
                # Ici appelle ta fabrique de signaux: self.generate_signal(symbol, ohlcv, ...)
                # Exemple factice: on incrémente juste les ticks.
                self.ticks_total += 1
                # -----------------------------

            except asyncio.CancelledError:
                raise
            except Exception as e:
                # Erreur de boucle symbole → on notifie mais on ne stoppe pas tout
                try:
                    await self.notifier.send(f"[{symbol}] loop error: {e}")
                except Exception:
                    pass
                await asyncio.sleep(1.0)

            # cadence
            await asyncio.sleep(0.2)

    async def _commands_loop(self):
        assert self.command_stream is not None
        async for cmd in self.command_stream:
            c = cmd.strip().lower()
            if c in ("/status", "status"):
                await self._send_status()

            elif c.startswith("/setup"):
                await self.notifier.send("🧩 Setup wizard à compléter (placeholder).")

            elif c.startswith("/backtest"):
                await self.notifier.send("🧪 Backtest en cours…")
                try:
                    await handle_backtest_command(self.notifier, self.symbols, timeframe=self.timeframe)
                except Exception as e:
                    await self.notifier.send(f"⚠️ Backtest : erreur inattendue: {e}")

            elif c in ("/resume", "resume"):
                self._state = "RUNNING"
                await self.notifier.send("🚀 Passage en RUNNING")

            elif c in ("/pause", "pause"):
                self._state = "PAUSED"
                await self.notifier.send("⏸️ Pause")

            elif c in ("/stop", "stop"):
                await self.notifier.send("🛑 Arrêt orchestrateur demandé.")
                await self.stop()
                break

            else:
                await self.notifier.send("ℹ️ Commandes: /status /setup /backtest /resume /pause /stop")

    async def _send_status(self):
        await self.notifier.send(
            "🟢 Orchestrator PRELAUNCH." if self._state == "PRELAUNCH"
            else ("🚀 RUNNING" if self._state == "RUNNING" else ("⏸️ PAUSED" if self._state == "PAUSED" else "🛑 STOPPED"))
            + f"\n• TF: {self.timeframe}\n• Symbols: {', '.join(self.symbols)}"
        )

    # ------------- life-cycle -------------
    async def start(self):
        # Notifier + commandes (fallback automatique)
        self.notifier, self.command_stream, notify_status = await build_notifier_and_commands()
        if not QUIET:
            print(f"[notify] {notify_status}")
        try:
            await self.notifier.send(
                f"🟢 Orchestrator PRELAUNCH.\nUtilise /setup ou /backtest. /resume pour démarrer le live."
            )
        except Exception:
            pass

        # tâches de fond: heartbeat + stats
        self._bg_tasks.append(
            asyncio.create_task(heartbeat_task(lambda: not self._closing))
        )
        self._bg_tasks.append(
            asyncio.create_task(log_stats_task(lambda: self.ticks_total, lambda: self.symbols))
        )

        # commandes Telegram (si dispo)
        if self.command_stream:
            self._bg_tasks.append(asyncio.create_task(self._commands_loop()))

        # boucles symboles
        for sym in self.symbols:
            self._symbol_tasks.append(asyncio.create_task(self._symbol_loop(sym)))

    async def stop(self):
        if self._closing:
            return
        self._closing = True
        self._state = "STOPPED"

        # stop tasks
        for t in self._symbol_tasks:
            t.cancel()
        for t in self._bg_tasks:
            t.cancel()
        await asyncio.gather(*self._symbol_tasks, return_exceptions=True)
        await asyncio.gather(*self._bg_tasks, return_exceptions=True)

        # fermer notifier/command stream
        if self.command_stream:
            try:
                await self.command_stream.stop()
            except Exception:
                pass
        try:
            await self.notifier.close()
        except Exception:
            pass

    # point d’entrée externe: l’orchestrateur tourne tant qu’on ne stoppe pas
    async def run(self):
        await self.start()
        # PRELAUNCH : on attend commandes /resume
        while not self._closing:
            await asyncio.sleep(0.5)

# ---------------------------------------------------------------------------

async def run_orchestrator(exchange: Any, config: Dict[str, Any]) -> None:
    """
    Point d’entrée appelé par bot.py
    config attend au minimum:
      - symbols: list[str]
      - timeframe: str
      - (optionnel) cash, risk_pct, ...
    """
    symbols = list(config.get("symbols") or [])
    timeframe = str(config.get("timeframe") or "5m")

    orch = Orchestrator(exchange, config, symbols, timeframe=timeframe)
    await orch.run()