"""Risk management utilities for position sizing."""

from __future__ import annotations

__all__ = [
    "calc_risk_amount",
    "calc_position_size",
    "adjust_risk_pct",
    "dynamic_risk_pct",
]


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


def adjust_risk_pct(
    risk_pct: float,
    win_streak: int,
    loss_streak: int,
    *,
    increase: float = 0.12,
    decrease: float = 0.25,
    min_pct: float = 0.001,
    max_pct: float = 0.05,
) -> float:
    """Return ``risk_pct`` adjusted by recent performance.

    After two consecutive winning trades the risk percentage is increased by
    ``increase`` (default 12%).  After two consecutive losses it is reduced by
    ``decrease`` (default 25%).  The result is bounded by ``min_pct`` and
    ``max_pct``.

    Parameters
    ----------
    risk_pct:
        Current risk fraction (e.g. ``0.01`` for 1%).  Must be positive.
    win_streak / loss_streak:
        Number of consecutive wins or losses.
    increase / decrease:
        Fractional adjustments applied when the respective streak is reached.
    min_pct / max_pct:
        Hard limits for the adjusted risk.
    """

    if risk_pct <= 0:
        raise ValueError("risk_pct must be positive")

    if win_streak >= 2:
        risk_pct *= 1.0 + increase
    if loss_streak >= 2:
        risk_pct *= 1.0 - decrease

    if risk_pct < min_pct:
        return min_pct
    if risk_pct > max_pct:
        return max_pct
    return risk_pct


def dynamic_risk_pct(risk_pct: float, pnl_pct: float, quality: str) -> float:
    """Adjust ``risk_pct`` based on last trade result and signal quality.

    The risk is reduced by 25% after a losing trade.  When the provided
    ``quality`` is ``"A"`` and the trade was not a loss, the risk is increased
    by 10%.  The value is always bounded to the ``[0.001, 0.05]`` interval.

    Parameters
    ----------
    risk_pct:
        Current risk fraction (e.g. ``0.01`` for 1%). Must be positive.
    pnl_pct:
        Percentage PnL of the last trade. A negative value denotes a loss.
    quality:
        Quality grade of the next setup. Only ``"A"`` triggers an increase.
    """

    if risk_pct <= 0:
        raise ValueError("risk_pct must be positive")

    if pnl_pct < 0:
        risk_pct *= 0.75
    elif quality.upper() == "A":
        risk_pct *= 1.10

    return max(0.001, min(0.05, risk_pct))
