from __future__ import annotations
import asyncio
from typing import AsyncIterator

class Scheduler:
    def __init__(self, interval_sec: int = 2):
        self.interval = max(1, int(interval_sec))

    async def ticks(self) -> AsyncIterator[int]:
        i = 0
        while True:
            yield i
            i += 1
            await asyncio.sleep(self.interval)
            