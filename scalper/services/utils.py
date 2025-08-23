# scalper/services/utils.py
from __future__ import annotations

import asyncio
import inspect
import random
import time
from typing import Any, Awaitable, Callable, Optional

QUIET = int((__import__("os").getenv("QUIET", "0") or "0"))

# ---------------------------------------------------------------------------
# safe_call: wrapper de retry exponentiel (sync/async), avec jitter
# ---------------------------------------------------------------------------

async def _async_sleep(sec: float) -> None:
    await asyncio.sleep(max(0.0, sec))

def _is_coro_fn(fn: Callable[..., Any]) -> bool:
    return inspect.iscoroutinefunction(fn)

async def safe_call(
    fn: Callable[..., Any],
    *args: Any,
    label: str = "",
    max_retries: int = 5,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
    jitter: float = 0.25,
    **kwargs: Any,
) -> Any:
    """
    Appelle fn(*args, **kwargs) avec retry exponentiel.
    - supporte les fonctions sync ET async.
    - lève la dernière exception si tous les essais échouent.
    """
    attempt = 0
    delay = float(base_delay)
    last_exc: Optional[BaseException] = None

    while attempt <= max_retries:
        try:
            if _is_coro_fn(fn):
                return await fn(*args, **kwargs)
            # sync -> exécuter dans un thread pour ne pas bloquer l'event loop
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))
        except BaseException as e:  # noqa: BLE001
            last_exc = e
            if attempt == max_retries:
                if not QUIET:
                    print(f"[safe_call] FAIL {label or fn.__name__}: {e}")
                raise
            # backoff + jitter
            jitter_val = random.uniform(-jitter, jitter) * delay
            sleep_for = min(max_delay, max(0.05, delay + jitter_val))
            if not QUIET:
                print(f"[safe_call] retry {attempt+1}/{max_retries} after {sleep_for:.2f}s ({label or fn.__name__})")
            await _async_sleep(sleep_for)
            delay = min(max_delay, delay * 2.0)
            attempt += 1

    # ne devrait pas arriver
    if last_exc:
        raise last_exc

# ---------------------------------------------------------------------------
# Tasks utilitaires (respectent QUIET=1)
# ---------------------------------------------------------------------------

async def heartbeat_task(
    running_getter: Callable[[], bool],
    *,
    period: float = 15.0,
    tag: str = "heartbeat",
) -> None:
    """
    Tâche légère qui signale que le process est vivant.
    """
    while running_getter():
        if not QUIET:
            print(f"[{tag}] alive")
        await asyncio.sleep(max(1.0, period))

async def log_stats_task(
    running_getter: Callable[[], bool],
    ticks_getter: Callable[[], int],
    symbols_getter: Callable[[], list[str] | tuple[str, ...] | Any],
    *,
    period: float = 30.0,
    tag: str = "stats",
) -> None:
    """
    Log périodique des stats: total de ticks et paires actives.
    Signature compatible avec l'appel de l'orchestrateur.
    """
    last_ticks = None
    while running_getter():
        try:
            ticks = int(ticks_getter() or 0)
            syms = symbols_getter()
            if not isinstance(syms, (list, tuple)):
                try:
                    syms = list(syms)
                except Exception:
                    syms = [str(syms)]
            if not QUIET:
                rate = "" if last_ticks is None else f" (+{ticks - last_ticks} /{int(period)}s)"
                print(f"[{tag}] ticks_total={ticks}{rate} | pairs={','.join(map(str, syms))}")
            last_ticks = ticks
        except Exception as e:
            if not QUIET:
                print(f"[{tag}] error: {e}")
        await asyncio.sleep(max(2.0, period))