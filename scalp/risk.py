"""Risk management utilities for position sizing."""

from __future__ import annotations

__all__ = ["calc_risk_amount", "calc_position_size"]


def calc_risk_amount(equity: float, risk_pct: float) -> float:
    """Return the monetary amount to risk on a trade.

    Parameters
    ----------
    equity: float
        Total account equity in quote currency.
    risk_pct: float
        Fraction of equity to risk (e.g. ``0.01`` for 1%). Must be in ``(0, 1]``.
    """
    if equity <= 0:
        raise ValueError("equity must be positive")
    if risk_pct <= 0 or risk_pct > 1:
        raise ValueError("risk_pct must be between 0 and 1")
    return equity * risk_pct


def calc_position_size(equity: float, risk_pct: float, stop_distance: float) -> float:
    """Compute position size given risk and stop distance.

    The size is ``risk_amount / stop_distance`` where ``risk_amount`` equals
    ``equity * risk_pct``.

    Parameters
    ----------
    equity: float
        Total account equity in quote currency.
    risk_pct: float
        Fraction of equity to risk (e.g. ``0.01`` for 1%).
    stop_distance: float
        Distance between entry price and stop-loss in quote currency.
        Must be positive.
    """
    if stop_distance <= 0:
        raise ValueError("stop_distance must be positive")
    risk_amount = calc_risk_amount(equity, risk_pct)
    return risk_amount / stop_distance
