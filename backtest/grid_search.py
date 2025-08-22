"""Grid-search express module to evaluate hyperparameter combinations.

This module builds combinations of strategy and engine parameters, runs the
existing multi symbol backtester for each combination, collects key metrics and
selects the best configuration according to:

1. Profit factor (descending)
2. Maximum drawdown percentage (ascending)
3. Net PnL in USDT (descending)
4. Number of trades (ascending)

Results are written under ``result/grid`` by default and a short summary is
printed to the console.
"""
from __future__ import annotations

from dataclasses import dataclass
import csv
import json
import os
import random
from itertools import product
from typing import Any, Callable, Dict, Iterable, List, Sequence

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def parse_hours(hours: str) -> List[int]:
    """Parse hours specification like ``"7-11,13-17"`` into a list of ints.

    Each comma separated element can either be a single hour (``"8"``) or a
    range ``"7-11"`` which is inclusive.  Returned hours are sorted and unique.
    """

    if not hours:
        return []
    result: List[int] = []
    for part in hours.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start, end = int(start_s), int(end_s)
            result.extend(range(start, end + 1))
        else:
            result.append(int(part))
    return sorted(set(result))


# Order of parameters used throughout the module and in CSV output
PARAM_KEYS = [
    "timeframe",
    "score_min",
    "atr_min_ratio",
    "rr_min",
    "risk_pct",
    "slippage_bps",
    "fee_rate",
    "cooldown_secs",
    "hours",
]

# Default values used if a parameter is not provided in the grid
DEFAULTS = {
    "score_min": 55,
    "atr_min_ratio": 0.002,
    "rr_min": 1.2,
    "risk_pct": 0.01,
    "slippage_bps": 2,
    "fee_rate": 0.001,
    "cooldown_secs": 300,
    "hours": "7-11,13-17",
}


@dataclass
class GridResult:
    params: Dict[str, Any]
    metrics: Dict[str, float]


def _ensure_list(val: Sequence[Any] | Any) -> List[Any]:
    if isinstance(val, (list, tuple, set)):
        return list(val)
    return [val]


def build_param_grid(param_lists: Dict[str, Sequence[Any]], grid_max: int) -> List[Dict[str, Any]]:
    """Return a list of parameter combinations.

    ``param_lists`` maps parameter names to a sequence of values.  Missing keys
    fall back to ``DEFAULTS``.  The resulting cartesian product is uniformly
    sampled to ``grid_max`` elements when necessary while trying to maintain a
    variety of timeframes and ``atr_min_ratio`` values.
    """

    lists: Dict[str, List[Any]] = {}
    for key in PARAM_KEYS:
        if key == "timeframe":
            # timeframe must be explicitly provided; default empty -> "1m"
            vals = param_lists.get(key) or ["1m"]
        else:
            vals = param_lists.get(key)
            if not vals:
                default = DEFAULTS[key]
                vals = [default]
        lists[key] = _ensure_list(vals)

    combos: List[Dict[str, Any]] = [
        dict(zip(PARAM_KEYS, values)) for values in product(*(lists[k] for k in PARAM_KEYS))
    ]

    # Uniform sampling if exceeding grid_max
    if len(combos) > grid_max:
        step = len(combos) / float(grid_max)
        sampled = []
        for i in range(grid_max):
            idx = int(round(i * step))
            if idx >= len(combos):
                idx = len(combos) - 1
            sampled.append(combos[idx])
        # ensure each timeframe appears at least once
        wanted_tfs = set(lists["timeframe"])
        present_tfs = {c["timeframe"] for c in sampled}
        missing = list(wanted_tfs - present_tfs)
        if missing:
            for tf in missing:
                for c in combos:
                    if c["timeframe"] == tf and c not in sampled:
                        sampled.append(c)
                        break
            sampled = sampled[:grid_max]
        combos = sampled
    return combos


# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------


def run_grid_search(
    *,
    symbols: Sequence[str],
    exchange: str,
    base_params: Dict[str, Any],
    param_lists: Dict[str, Sequence[Any]],
    grid_max: int = 12,
    csv_dir: str | None = None,
    initial_equity: float = 1000.0,
    leverage: float = 1.0,
    paper_constraints: bool = True,
    seed: int | None = None,
    out_dir: str = "./result/grid",
    match_exchange_semantics: bool = False,  # placeholder for compatibility
    run_func: Callable[..., Any] | None = None,
) -> List[GridResult]:
    """Execute grid search across parameter combinations.

    ``base_params`` provides default single values for parameters. ``param_lists``
    contains the grid specifications from CLI (already parsed into sequences).
    ``run_func`` should have the same signature as :func:`run_backtest_multi`.
    """

    if seed is not None:
        random.seed(seed)

    if run_func is None:  # avoid circular import at module load
        from .run_multi import run_backtest_multi  # late import

        run_func = run_backtest_multi

    # merge lists with defaults
    full_lists: Dict[str, Sequence[Any]] = {}
    for k in PARAM_KEYS:
        if k == "timeframe":
            full_lists[k] = param_lists.get(k) or [base_params.get("timeframe", "1m")]
        else:
            if param_lists.get(k) is not None:
                full_lists[k] = param_lists[k]
            else:
                full_lists[k] = [base_params.get(k, DEFAULTS[k])]

    combos = build_param_grid(full_lists, grid_max)

    results: List[GridResult] = []
    os.makedirs(out_dir, exist_ok=True)

    for combo in combos:
        # Build parameters for backtester
        tf = combo["timeframe"]
        fee = float(combo["fee_rate"])
        slip = float(combo["slippage_bps"])
        risk = float(combo["risk_pct"])

        summary, _trades = run_func(
            symbols=list(symbols),
            exchange=exchange,
            timeframe=tf,
            csv_dir=csv_dir,
            fee_rate=fee,
            slippage_bps=slip,
            risk_pct=risk,
            initial_equity=initial_equity,
            leverage=leverage,
            paper_constraints=paper_constraints,
            seed=seed,
            out_dir=os.path.join(out_dir, "tmp"),
            plot=False,
            dry_run=True,
        )
        total = next((r for r in summary if r.get("symbol") == "TOTAL"), summary[-1])
        metrics = {
            "pnl_usdt": float(total.get("pnl_usdt", 0.0)),
            "profit_factor": float(total.get("profit_factor", 0.0)),
            "max_dd_pct": float(total.get("max_drawdown_pct", 0.0)),
            "winrate_pct": float(total.get("winrate_pct", 0.0)),
            "trades": float(total.get("trades", 0.0)),
            "final_equity": initial_equity + float(total.get("pnl_usdt", 0.0)),
        }
        results.append(GridResult(params=combo, metrics=metrics))

    # sort results
    results.sort(
        key=lambda r: (
            -r.metrics["profit_factor"],
            r.metrics["max_dd_pct"],
            -r.metrics["pnl_usdt"],
            r.metrics["trades"],
        )
    )

    # console output -------------------------------------------------------
    print(
        f"Grid-search express ({len(results)} combinaisons testées, top trié par PF↓ puis MaxDD%↑)"
    )
    header = (
        f"{'timeframe':<8} {'PF':>6} {'MaxDD%':>8} {'PnL':>8} {'Trades':>8}"
    )
    print(header)
    for r in results[:10]:
        m = r.metrics
        print(
            f"{r.params['timeframe']:<8} {m['profit_factor']:>6.2f} {m['max_dd_pct']:>8.2f} {m['pnl_usdt']:>8.2f} {int(m['trades']):>8}"
        )

    # write csv ------------------------------------------------------------
    csv_cols = PARAM_KEYS + [
        "pnl_usdt",
        "profit_factor",
        "max_dd_pct",
        "winrate_pct",
        "trades",
        "final_equity",
    ]
    with open(os.path.join(out_dir, "grid_results.csv"), "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=csv_cols)
        writer.writeheader()
        for r in results:
            row = {**r.params, **r.metrics}
            writer.writerow(row)

    best = results[0]
    with open(os.path.join(out_dir, "best_config.json"), "w", encoding="utf8") as fh:
        json.dump({"params": best.params, "metrics": best.metrics}, fh, indent=2)

    # markdown summary -----------------------------------------------------
    md_path = os.path.join(out_dir, "grid_summary.md")
    with open(md_path, "w", encoding="utf8") as fh:
        fh.write(
            "| timeframe | PF | MaxDD% | PnL | trades |\n|---|---|---|---|---|\n"
        )
        for r in results[:10]:
            m = r.metrics
            fh.write(
                f"| {r.params['timeframe']} | {m['profit_factor']:.2f} | {m['max_dd_pct']:.2f} | {m['pnl_usdt']:.2f} | {int(m['trades'])} |\n"
            )

    # optional scatter plot ------------------------------------------------
    try:  # pragma: no cover - optional dependency
        import matplotlib.pyplot as plt

        pf = [r.metrics["profit_factor"] for r in results]
        dd = [r.metrics["max_dd_pct"] for r in results]
        trades = [r.metrics["trades"] for r in results]
        tfs = [r.params["timeframe"] for r in results]
        colors = {tf: i for i, tf in enumerate(sorted(set(tfs)))}
        c = [colors[tf] for tf in tfs]
        plt.figure(figsize=(6, 4))
        plt.scatter(dd, pf, c=c, s=[max(10, t) for t in trades], alpha=0.7)
        plt.xlabel("MaxDD%")
        plt.ylabel("Profit Factor")
        plt.title("PF vs MaxDD")
        plt.savefig(os.path.join(out_dir, "pf_vs_dd.png"))
        plt.close()
    except Exception:  # pragma: no cover
        pass

    return results


__all__ = ["run_grid_search", "build_param_grid", "parse_hours", "GridResult"]
