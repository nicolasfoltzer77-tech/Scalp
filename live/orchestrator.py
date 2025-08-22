from __future__ import annotations
import asyncio
from typing import Sequence
from scalp.adapters.bitget import BitgetFuturesClient
from scalp.services.order_service import OrderService


class Orchestrator:
    def __init__(self, exchange: BitgetFuturesClient, order_service: OrderService, config):
        self.exchange = exchange
        self.order_service = order_service
        self.config = config
        self._running = False

    async def _task_refresh_watchlist(self):
        while self._running:
            await asyncio.sleep(30)

    async def _task_trade_loop(self, symbol: str):
        while self._running:
            await asyncio.sleep(1)

    async def run(self, symbols: Sequence[str]):
        self._running = True
        tasks = [asyncio.create_task(self._task_refresh_watchlist())] + [
            asyncio.create_task(self._task_trade_loop(s)) for s in symbols
        ]
        try:
            await asyncio.gather(*tasks)
        finally:
            self._running = False
            for t in tasks:
                t.cancel()
