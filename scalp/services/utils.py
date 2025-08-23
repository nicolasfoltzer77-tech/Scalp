# scalp/services/utils.py
from __future__ import annotations

import asyncio
import inspect
import time
from typing import Any, Callable, Optional


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
    - fn      : lambda sans argument qui retourne un objet ou une coroutine
    - label   : tag lisible dans les logs
    - running_flag : fonction booléenne (ex: lambda: orch._running) pour sortir proprement

    Retourne la valeur de fn (ou None si on a dû abandonner).
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
            print(f"[safe:{label}] {e!r} -> retry in {delay:.1f}s")
            await asyncio.sleep(delay)
            delay = min(backoff_max, delay * 1.7)


async def heartbeat_task(get_running: Callable[[], bool], period: float = 15.0) -> None:
    """Petit heartbeat périodique lisible dans le terminal."""
    while get_running():
        print("[heartbeat] alive")
        await asyncio.sleep(period)


async def log_stats_task(
    get_running: Callable[[], bool],
    *,
    get_ticks: Callable[[], int],
    get_pairs: Callable[[], int],
    period: float = 30.0,
) -> None:
    """
    Affiche des stats périodiques (ticks cumulés, nb de paires).
    - get_ticks : fonction qui retourne le cumul des ticks vus depuis le boot
    - get_pairs : fonction qui retourne le nombre de paires actives
    """
    last_t = time.time()
    last_ticks = get_ticks()
    while get_running():
        await asyncio.sleep(period)
        now = time.time()
        ticks = get_ticks()
        dt = max(1.0, now - last_t)
        d_ticks = max(0, ticks - last_ticks)
        rate = d_ticks / dt
        print(f"[stats] ticks_total={ticks} (+{d_ticks}) rate={rate:.1f}/s | pairs={get_pairs()}")
        last_t, last_ticks = now, ticks