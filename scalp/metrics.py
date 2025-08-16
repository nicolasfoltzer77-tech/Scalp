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


def backtest_position(prices: list[float], entry_idx: int, exit_idx: int, side: int) -> bool:
    """Run a basic backtest to verify a position's coherence.

    Parameters
    ----------
    prices: list[float]
        Sequential list of prices to evaluate.
    entry_idx: int
        Index in ``prices`` where the position is opened.
    exit_idx: int
        Index in ``prices`` where the position is closed (must be > ``entry_idx``).
    side: int
        +1 for long, -1 for short.

    Returns
    -------
    bool
        ``True`` if the resulting PnL is non-negative, meaning the position is
        coherent with the direction of price movement. ``False`` otherwise.
    """
    if side not in (1, -1):
        raise ValueError("side must be +1 (long) or -1 (short)")
    if not (0 <= entry_idx < exit_idx < len(prices)):
        raise ValueError("entry_idx and exit_idx must be valid and entry_idx < exit_idx")

    entry_price = float(prices[entry_idx])
    exit_price = float(prices[exit_idx])
    pnl = calc_pnl_pct(entry_price, exit_price, side)
    return pnl >= 0.0
