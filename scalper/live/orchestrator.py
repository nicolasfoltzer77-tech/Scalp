# scalper/live/orchestrator.py
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Tuple

from scalper.live.watchlist import make_watchlist_manager, WatchlistManager
from scalper.live.ohlcv_service import OhlcvService  # assumed existing
from scalper.hooks.prewarm_cache import prewarm_cache  # assumed existing


@dataclass
class RunConfig:
    timeframe: str = "5m"
    refresh_s: int = 300
    risk_pct: float = 0.05
    slippage_bps: float = 0.0


class Orchestrator:
    def __init__(
        self,
        exchange: Any,
        run_cfg: RunConfig,
        notifier: Any,
        command_stream: Any,
        watchlist: Optional[WatchlistManager] = None,
    ) -> None:
        self.exchange = exchange
        self.cfg = run_cfg
        self.notifier = notifier
        self.command_stream = command_stream
        self.watchlist = watchlist or make_watchlist_manager()

        self._bg_tasks: List[asyncio.Task] = []
        self._running = False
        self._ticks_total = 0

        self._ohlcv = OhlcvService(exchange=self.exchange, timeframe=self.cfg.timeframe)

    # ------------------------------------------------------------------ tasks
    async def _heartbeat_task(self) -> None:
        while self._running:
            try:
                await self.notifier.send("heartbeat alive")
            except Exception:
                pass
            await asyncio.sleep(30)

    async def _stats_task(self) -> None:
        while self._running:
            try:
                pairs = ", ".join(self.watchlist.pairs)
                await self.notifier.send(f"[stats] ticks_total={self._ticks_total} (+0 /30s) | pairs={pairs}")
            except Exception:
                pass
            await asyncio.sleep(30)

    # --------------------------------------------------------------- life-cycle
    async def start(self) -> None:
        # PRELAUNCH banner already sent by notify builder; repeat here in case of null notifier
        try:
            await self.notifier.send("Orchestrator PRELAUNCH. Utilise /setup ou /backtest. /resume pour démarrer le live.")
        except Exception:
            pass

        # Warm cache (non‑fatal)
        try:
            prewarm_cache(self.exchange, top_n=10, timeframe=self.cfg.timeframe)
        except Exception:
            pass

        # Build initial watchlist (this is what was missing)
        self.watchlist.boot(exchange=self.exchange)

        self._running = True
        self._bg_tasks = [
            asyncio.create_task(self._heartbeat_task()),
            asyncio.create_task(self._stats_task()),
        ]

    async def stop(self) -> None:
        self._running = False
        for t in self._bg_tasks:
            t.cancel()
        self._bg_tasks.clear()

    async def run(self) -> None:
        await self.start()
        try:
            # Minimal live loop: fetch last candle for each pair just to bump ticks
            while self._running:
                if not self.watchlist.pairs:
                    await asyncio.sleep(1.0)
                    continue
                await asyncio.gather(*(self._ohlcv.fetch_last(symbol) for symbol in self.watchlist.pairs))
                self._ticks_total += len(self.watchlist.pairs)
                await asyncio.sleep(1.0)
        finally:
            await self.stop()


# ---------------------------------------------------------------- entry point
async def run_orchestrator(exchange: Any, cfg: RunConfig, notifier: Any, command_stream: Any) -> None:
    orch = Orchestrator(exchange=exchange, run_cfg=cfg, notifier=notifier, command_stream=command_stream)
    await orch.run()