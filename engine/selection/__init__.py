"""Pair selection helpers for the Scalp bot.

This package exposes two utilities used during the preparation phase of the
trading strategy:

``scan_pairs``
    Performs the first level market scan by filtering pairs based on volume,
    spread and hourly volatility.

``select_active_pairs``
    Refines a list of pairs by keeping only those showing an EMA20/EMA50
    crossover and a sufficiently high ATR.
"""

from .scanner import scan_pairs
from .momentum import select_active_pairs

__all__ = ["scan_pairs", "select_active_pairs"]

