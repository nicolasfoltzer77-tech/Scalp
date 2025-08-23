# scalper/live/orchestrator.py
from __future__ import annotations

import asyncio
import os
from typing import Any, Callable, Awaitable

from scalper.live.notify import build_notifier_and_commands, BaseNotifier, CommandStream
from scalper.services.utils import safe_call, heartbeat_task, log_stats_task


class Orchestrator:
    """
    Orchestrateur live minimal, IO protégés par safe_call, notifier décorrélé.
    """

    def __init__(
        self,
        exchange: Any,
        config: dict[str, Any],
        symbols: list[str],
        notifier: BaseNotifier,
        command_stream: CommandStream,
    ) -> None:
        self.exchange = exchange
        self.config = config
        self.symbols = symbols
        self.notifier = notifier
        self.command_stream = command_stream

        self.timeframe = str(config.get("TIMEFRAME", "5m"))
        self._running = False
        self._bg_tasks: list[asyncio.Task[Any]] = []

        self.ticks_total = 0

        # fonctions d’IO attendues sur exchange
        # - fetch_ohlcv(symbol, timeframe, limit) -> list | any
        self.fetch_ohlcv: Callable[[str, str, int], Awaitable[Any]] = getattr(
            exchange, "fetch_ohlcv", None
        )
        if self.fetch_ohlcv is None:
            async def _missing(*_a: Any, **_k: Any) -> Any:
                raise RuntimeError("Brancher fetch_ohlcv sur ta source historique/CCXT.")
            self.fetch_ohlcv = _missing  # type: ignore[assignment]

    # ---------------------------- lifecycle ----------------------------

    async def start(self) -> None:
        self._running = False  # PRELAUNCH
        quiet = os.environ.get("QUIET", "0") == "1"

        # Background tasks (heartbeat + stats)
        self._bg_tasks.append(
            asyncio.create_task(heartbeat_task(lambda: True, self.notifier, label="orchestrator"))
        )
        self._bg_tasks.append(
            asyncio.create_task(
                log_stats_task(lambda: self.ticks_total, lambda: self.symbols, self.notifier, interval=30)
            )
        )

        # PRELAUNCH message
        pairs = ",".join(self.symbols)
        tf = self.timeframe
        await self._safe_notify(
            f"🟢 Orchestrator PRELAUNCH.\n"
            f"Utilise /setup ou /backtest. /resume pour démarrer le live.\n"
            f"[watchlist] boot got: [{pairs}] (tf={tf})"
        )
        if not quiet:
            print("[orchestrator] PRELAUNCH")

    async def run(self) -> None:
        """
        Boucles symboles. Démarre après /resume ou dès qu'on met _running=True.
        """
        await self.start()

        # Ici on démarre directement (tu peux brancher une commande /resume)
        self._running = True

        # lancer tâches par symbole
        loops = [asyncio.create_task(self._symbol_loop(sym)) for sym in self.symbols]
        try:
            await asyncio.gather(*loops)
        finally:
            for t in self._bg_tasks:
                t.cancel()
            await asyncio.gather(*self._bg_tasks, return_exceptions=True)

    # ----------------------------- loops ------------------------------

    async def _symbol_loop(self, symbol: str) -> None:
        """
        Boucle principale par symbole : fetch OHLCV en boucle (protégé par safe_call).
        """
        limit = int(self.config.get("FETCH_LIMIT", 1000))
        while self._running:
            try:
                # tous les IO via safe_call
                _ = await safe_call(
                    self.fetch_ohlcv, symbol, self.timeframe, limit, label=f"ohlcv:{symbol}"
                )
                self.ticks_total += 1
            except Exception as e:  # noqa: BLE001
                await self._safe_notify(f"[{symbol}] loop error: {e}")
                await asyncio.sleep(1.0)
            await asyncio.sleep(0)  # yield

    # ----------------------------- helpers ----------------------------

    async def _safe_notify(self, text: str) -> None:
        try:
            await self.notifier.send(text)
        except Exception:
            pass


# ----------------------------- façade -------------------------------

async def run_orchestrator(exchange: Any, run_config: dict[str, Any]) -> None:
    """
    Point d’entrée unique utilisé par bot.py :
    - construit notifier/command_stream depuis la config
    - instancie l’orchestrateur
    - exécute .run()
    """
    # Build notifier/commands à partir de la config (ou env)
    notifier, command_stream = await build_notifier_and_commands(run_config)

    # Watchlist
    symbols = list(run_config.get("TOP_SYMBOLS", []))
    if not symbols:
        # Liste par défaut si rien n'est fourni
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
                   "DOGEUSDT", "ADAUSDT", "LTCUSDT", "AVAXUSDT", "LINKUSDT"]

    orch = Orchestrator(exchange, run_config, symbols, notifier, command_stream)
    await orch.run()