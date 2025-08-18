from __future__ import annotations

"""Parameter sweep utilities for strategy optimisation.

This module performs a grid search over a parameter space in parallel.  It
tries to use :mod:`ray` for distributed execution when available and falls
back to :mod:`multiprocessing` otherwise.
"""

import itertools
import json
import multiprocessing as mp
import os
from typing import Any, Dict, Iterable, List, Sequence

try:  # Optional dependency
    import ray  # type: ignore
except Exception:  # pragma: no cover - ray is optional
    ray = None

from scalp.backtest import backtest_trades


# ---------------------------------------------------------------------------
# Parameter space
# ---------------------------------------------------------------------------

def param_space_default() -> Dict[str, Sequence[Any]]:
    """Return the default parameter search space.

    The keys correspond to strategy parameters while the values are iterables
    of possible settings.  The defaults represent a small but representative
    grid and can be overridden by callers.
    """

    return {
        "ema_fast": [10, 20, 30],
        "ema_slow": [50, 100, 200],
        "rsi_period": [14, 21],
        "atr_period": [14, 21],
    }


def _param_grid(space: Dict[str, Iterable[Any]]) -> List[Dict[str, Any]]:
    """Expand *space* into a list of parameter combinations."""

    keys = list(space)
    values = [space[k] for k in keys]
    return [dict(zip(keys, combo)) for combo in itertools.product(*values)]


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def eval_params_one(grid_item: Dict[str, Any]) -> Dict[str, Any]:
    """Run a backtest for a single parameter combination.

    ``grid_item`` contains the parameter values along with optional ``trades``
    to evaluate.  The function returns a copy of the parameters augmented with
    the computed PnL under the key ``pnl``.
    """

    params = dict(grid_item)
    trades = params.pop("trades", [])
    fee_rate = params.pop("fee_rate", None)
    zero_fee = params.pop("zero_fee_pairs", None)
    pnl = backtest_trades(trades, fee_rate=fee_rate, zero_fee_pairs=zero_fee)
    params["pnl"] = pnl
    return params


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_param_sweep(space: Dict[str, Iterable[Any]] | None = None, *, jobs: int | None = None) -> List[Dict[str, Any]]:
    """Evaluate the full parameter grid in parallel and return results."""

    space = space or param_space_default()
    grid = _param_grid(space)

    # Determine execution backend
    use_ray = False
    if ray is not None:
        try:  # pragma: no cover - depends on ray
            ray.init(ignore_reinit_error=True)
            use_ray = True
        except Exception:
            use_ray = False

    if use_ray:
        remote_eval = ray.remote(eval_params_one)  # type: ignore
        futures = [remote_eval.remote(g) for g in grid]
        results = ray.get(futures)
    else:
        jobs = jobs or int(os.getenv("OPT_JOBS", "0")) or mp.cpu_count()
        with mp.Pool(processes=jobs) as pool:
            results = pool.map(eval_params_one, grid)

    return results


def optimize(space: Dict[str, Iterable[Any]] | None = None, *, outfile: str = "opt_results.json", jobs: int | None = None) -> List[Dict[str, Any]]:
    """High level helper executing the sweep and saving aggregated results."""

    results = run_param_sweep(space, jobs=jobs)
    with open(outfile, "w", encoding="utf8") as fh:
        json.dump(results, fh, indent=2, sort_keys=True)
    return results


def main() -> None:  # pragma: no cover - convenience CLI
    optimize()


if __name__ == "__main__":  # pragma: no cover
    main()
