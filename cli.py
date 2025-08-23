"""Command line utilities for the Scalp project.

This module exposes a small command line interface used throughout the
project.  The actual trading logic lives in other modules, however the CLI is
responsible for parsing parameters and dispatching the appropriate routines.

The implementation intentionally keeps the invoked functions minimal so that
tests can patch them easily.  In a real deployment these functions would
perform optimisation, walk‑forward analysis or run the live pipeline.
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Iterable, List

from scalper.version import bump_version_from_git


# ---------------------------------------------------------------------------
# Placeholder implementations
# ---------------------------------------------------------------------------


def run_parallel_optimization(pairs: List[str], timeframe: str, jobs: int) -> None:
    """Run a parallel parameter optimisation.

    The real project dispatches a potentially heavy optimisation routine.  The
    function is kept trivial so unit tests can verify that the CLI wiring works
    without actually performing the optimisation.
    """

    print(f"Optimising {pairs} on {timeframe} with {jobs} jobs")


def run_walkforward_analysis(
    pair: str, timeframe: str, splits: int, train_ratio: float
) -> None:
    """Execute a walk-forward analysis."""

    print(
        f"Walk-forward on {pair} ({timeframe}), splits={splits}, train_ratio={train_ratio}"
    )


async def run_live_pipeline(pairs: List[str], tfs: Iterable[str]) -> None:
    """Run the live trading pipeline."""

    print(f"Running live pipeline for pairs={pairs} on tfs={list(tfs)}")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def create_parser() -> argparse.ArgumentParser:
    """Create the top-level argument parser."""

    parser = argparse.ArgumentParser(description="Scalp command line tools")
    sub = parser.add_subparsers(dest="command")

    # --- ``opt`` command -------------------------------------------------
    opt_p = sub.add_parser("opt", help="run optimisation in parallel")
    opt_p.add_argument("--pairs", nargs="+", required=True, help="trading pairs")
    opt_p.add_argument("--tf", required=True, help="timeframe")
    opt_p.add_argument("--jobs", type=int, default=1, help="number of workers")
    opt_p.set_defaults(
        func=lambda a: run_parallel_optimization(a.pairs, a.tf, a.jobs)
    )

    # --- ``walkforward`` command ----------------------------------------
    wf_p = sub.add_parser("walkforward", help="perform walk-forward analysis")
    wf_p.add_argument("--pair", required=True, help="trading pair")
    wf_p.add_argument("--tf", required=True, help="timeframe")
    wf_p.add_argument("--splits", type=int, default=1, help="number of splits")
    wf_p.add_argument(
        "--train-ratio",
        type=float,
        default=0.7,
        help="portion of data used for training",
    )
    wf_p.set_defaults(
        func=lambda a: run_walkforward_analysis(
            a.pair, a.tf, a.splits, a.train_ratio
        )
    )

    # --- ``live`` command -----------------------------------------------
    live_p = sub.add_parser("live", help="run the live async pipeline")
    live_p.add_argument("--pairs", nargs="+", required=True, help="trading pairs")
    live_p.add_argument("--tfs", nargs="+", required=True, help="timeframes")
    live_p.set_defaults(func=lambda a: asyncio.run(run_live_pipeline(a.pairs, a.tfs)))

    # --- ``bump-version`` command -------------------------------------
    bv_p = sub.add_parser(
        "bump-version",
        help="update the VERSION file based on the latest git commit",
    )
    bv_p.set_defaults(func=lambda a: print(bump_version_from_git()))

    return parser


def main(argv: Iterable[str] | None = None) -> int:
    """Entry point used by tests and ``if __name__ == '__main__'`` block."""

    parser = create_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    result = args.func(args)
    return 0 if result is None else int(result)


if __name__ == "__main__":  # pragma: no cover - manual invocation
    raise SystemExit(main())

