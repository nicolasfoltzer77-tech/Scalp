"""Optimization helpers using multiprocessing."""
from __future__ import annotations

from multiprocessing import Pool
from typing import Any, Callable, Sequence

__all__ = ["run_parallel"]


def run_parallel(func: Callable[[Any], Any], args: Sequence[Any], processes: int | None = None) -> list[Any]:
    """Execute ``func`` over ``args`` in parallel and return the results.

    The returned list preserves the order of ``args``. ``processes`` controls the
    number of worker processes, defaulting to the system's CPU count.
    """
    with Pool(processes=processes) as pool:
        return pool.map(func, args)
