# scalper/services/utils.py
from __future__ import annotations

import asyncio
import functools
import os
import time
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")


# ---------------------------------------------------------------------
# Retry commun (sync/async)
# ---------------------------------------------------------------------
async def _async_sleep(seconds: float) -> None:
    await asyncio.sleep(seconds)


def _sync_sleep(seconds: float) -> None:
    time.sleep(seconds)


def _is_coro_fn(fn: Callable[..., Any]) -> bool:
    return asyncio.iscoroutinefunction(fn)


async def safe_call(
    fn: Callable[..., T] | Callable[..., Awaitable[T]],
    *args: Any,
    label: str = "call",
    retries: int = 5,
    backoff: float = 0.4,
    backoff_mul: float = 1.6,
    **kwargs: Any,
) -> T:
    """
    Appelle fn avec retry exponentiel.
    Supporte fn sync/async.
    """
    attempt = 0
    delay = backoff
    while True:
        try:
            if _is_coro_fn(fn):
                return await fn(*args, **kwargs)  # type: ignore[misc]
            # sync
            return functools.partial(fn, *args, **kwargs)()  # type: ignore[misc]
        except Exception as e:  # noqa: BLE001
            attempt += 1
            if attempt > retries:
                raise
            print(f"[safe_call] retry {attempt}/{retries} after {delay:.2f}s ({label})")
            if asyncio.get_event_loop().is_running():
                await _async_sleep(delay)
            else:
                _sync_sleep(delay)
            delay *= backoff_mul


# ---------------------------------------------------------------------
# Tasks utilitaires
# ---------------------------------------------------------------------
async def heartbeat_task(
    running_getter: Callable[[], bool],
    notifier: Any,
    label: str = "orchestrator",
    period: float = 30.0,
) -> None:
    """
    Envoie un heartbeat périodique tant que running_getter() est True.
    """
    quiet = os.environ.get("QUIET", "0") == "1"
    try:
        while running_getter():
            if not quiet:
                print("[heartbeat] alive")
            try:
                await notifier.send(f"[{label}] heartbeat alive")
            except Exception:
                pass
            await asyncio.sleep(period)
    except asyncio.CancelledError:  # graceful stop
        return


async def log_stats_task(
    ticks_getter: Callable[[], int],
    symbols_getter: Callable[[], list[str] | tuple[str, ...]],
    notifier: Any,
    interval: float = 30.0,
) -> None:
    """
    Log périodique des stats (ticks_total + pairs).
    """
    quiet = os.environ.get("QUIET", "0") == "1"
    last = ticks_getter()
    try:
        while True:
            await asyncio.sleep(interval)
            now = ticks_getter()
            delta = now - last
            last = now
            pairs = ",".join(symbols_getter())
            if not quiet:
                print(f"[stats] ticks_total={now} (+{delta} /{int(interval)}s) | pairs={pairs}")
            try:
                await notifier.send(f"[stats] ticks_total={now} (+{delta} /{int(interval)}s)")
            except Exception:
                pass
    except asyncio.CancelledError:
        return