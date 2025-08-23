# scalp/services/utils.py
from __future__ import annotations

import asyncio
import inspect
import os
import time
from typing import Any, Callable, Optional

QUIET = os.getenv("QUIET", "0") == "1"


async def safe_call(
    fn: Callable[[], Any],
    *,
    label: str = "call",
    backoff_start: float = 1.0,
    backoff_max: float = 30.0,
    running_flag: Optional[Callable[[], bool]] = None,
) -> Any:
    """
    Enveloppe de sécurité commune (sync/async) avec retry exponentiel.
    - fn : lambda sans arg qui retourne un objet ou une coroutine
    - running_flag : fonction booléenne pour sortir proprement
    """
    delay = backoff_start
    while True:
        if running_flag and not running_flag():
            return None
        try:
            res = fn()
            if inspect.iscoroutine(res):
                return await res
            return res
        except asyncio.CancelledError:
            raise
        except Exception as e:
            if not QUIET:
                print(f"[safe:{label}] {e!r} -> retry in {delay:.1f}s")
            await asyncio.sleep(delay)
            delay = min(backoff_max, delay * 1.7)


async def heartbeat_task(get_running: Callable[[], bool], period: float = 15.0) -> None:
    """Heartbeat périodique (silencieux si QUIET=1)."""
    while get_running():
        if not QUIET:
            print("[heartbeat] alive")
        await asyncio.sleep(period)


async def log_stats_task(
    get_running: Callable[[], bool],
    *,
    get_ticks: Callable[[], int],
    get_pairs: Callable[[], int],
    period: float = 30.0,
) -> None:
    """Stats périodiques (ralenties et/ou masquées si QUIET=1)."""
    last_t = time.time()
    last_ticks = get_ticks()
    while get_running():
        await asyncio.sleep(120.0 if QUIET else period)
        now = time.time()
        ticks = get_ticks()
        dt = max(1.0, now - last_t)
        d_ticks = max(0, ticks - last_ticks)
        rate = d_ticks / dt
        if not QUIET:
            print(f"[stats] ticks_total={ticks} (+{d_ticks}) rate={rate:.1f}/s | pairs={get_pairs()}")
        last_t, last_ticks = now, ticks