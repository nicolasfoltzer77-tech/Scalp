# scalper/services/utils.py
from __future__ import annotations
import asyncio
from typing import Callable, Any


class NullNotifier:
    async def send(self, _msg: str) -> None:
        return


async def heartbeat_task(running_getter: Callable[[], bool], notifier: Any, period: float = 30.0) -> None:
    if notifier is None:
        notifier = NullNotifier()
    try:
        while running_getter():
            await notifier.send("heartbeat alive")
            await asyncio.sleep(period)
    except asyncio.CancelledError:
        pass


async def log_stats_task(
    notifier: Any,
    ticks_getter: Callable[[], int],
    symbols_getter: Callable[[], list[str]],
    period: float = 30.0,
) -> None:
    if notifier is None:
        notifier = NullNotifier()
    last = 0
    try:
        while True:
            total = int(ticks_getter() or 0)
            delta = total - last
            last = total
            syms = symbols_getter() or []
            msg = f"[stats] ticks_total={total} (+{delta} /30s) | pairs=" + ",".join(syms)
            print(msg)
            await notifier.send(msg)
            await asyncio.sleep(period)
    except asyncio.CancelledError:
        pass