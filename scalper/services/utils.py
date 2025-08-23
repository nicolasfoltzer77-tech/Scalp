# scalper/services/utils.py
from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, Optional

# ---------------------------------------------------------------------
# safe_call : retry exponentiel (async/sync)
# ---------------------------------------------------------------------
def _sleep(s: float) -> Awaitable[None]:
    return asyncio.sleep(s)

async def safe_call(
    fn: Callable[..., Any],
    label: str = "",
    *args: Any,
    retries: int = 5,
    base_delay: float = 0.4,
    max_delay: float = 5.0,
    **kwargs: Any,
) -> Any:
    """
    Appelle fn(*args, **kwargs) avec retry exponentiel.
    - fn peut être sync ou async.
    """
    attempt = 0
    delay = base_delay
    while True:
        try:
            res = fn(*args, **kwargs)
            if asyncio.iscoroutine(res):
                return await res
            return res
        except Exception as e:  # noqa: BLE001
            attempt += 1
            if attempt > retries:
                raise
            print(f"[safe_call] retry {attempt}/{retries} after {delay:.2f}s (ohlcv:{label})")
            await _sleep(delay)
            delay = min(delay * 2.0, max_delay)

# ---------------------------------------------------------------------
# heartbeat : envoie un "alive" régulier (respecte QUIET=1 côté notifier)
# ---------------------------------------------------------------------
async def heartbeat_task(
    running_getter: Callable[[], bool],
    notifier: Any,
    interval: float = 30.0,
    name: str = "orchestrator",
) -> None:
    """
    running_getter() -> bool
    notifier.send(text: str) -> coroutine
    """
    try:
        while running_getter():
            try:
                await notifier.send("[heartbeat] alive")
            except Exception:
                pass
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        pass

# ---------------------------------------------------------------------
# log stats
# ---------------------------------------------------------------------
async def log_stats_task(
    ticks_getter: Callable[[], int],
    symbols_getter: Callable[[], list[str]],
    snapshot_getter: Callable[[], dict[str, Any]],
    interval: float = 30.0,
) -> None:
    """
    ticks_getter() -> int
    symbols_getter() -> list[str]
    snapshot_getter() -> dict (libre) pour enrichir les logs/CSV si besoin
    """
    t0 = time.time()
    last = ticks_getter()
    try:
        while True:
            await asyncio.sleep(interval)
            cur = ticks_getter()
            add = cur - last
            last = cur
            pairs = ",".join(symbols_getter()) or "-"
            print(f"[stats] ticks_total={cur} (+{add} /{int(interval)}s) | pairs={pairs}")
            _ = snapshot_getter()  # hook, non utilisé ici
    except asyncio.CancelledError:
        pass