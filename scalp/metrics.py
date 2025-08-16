"""Utility metrics for trading calculations."""
from __future__ import annotations

def calc_pnl_pct(entry_price: float, exit_price: float, side: int) -> float:
    """Return percentage PnL between entry and exit prices.

    Parameters
    ----------
    entry_price: float
        Trade entry price (>0).
    exit_price: float
        Trade exit price (>0).
    side: int
        +1 for long, -1 for short.
    """
    if entry_price <= 0 or exit_price <= 0:
        raise ValueError("Prices must be positive")
    if side not in (1, -1):
        raise ValueError("side must be +1 (long) or -1 (short)")
    return (exit_price - entry_price) / entry_price * 100.0 * side
