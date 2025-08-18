"""Utility metrics for trading calculations."""
from __future__ import annotations


from typing import Iterable, Sequence

__all__ = ["calc_pnl_pct", "calc_rsi", "calc_atr", "backtest_position"]



def calc_pnl_pct(entry_price: float, exit_price: float, side: int, fee_rate: float = 0.0) -> float:
    """Return percentage PnL between entry and exit prices minus fees.


    Parameters
    ----------
    entry_price: float
        Trade entry price (>0).
    exit_price: float
        Trade exit price (>0).
    side: int
        +1 for long, -1 for short.
    fee_rate: float, optional
        Trading fee rate per operation (e.g., 0.0006 for 0.06%). The fee is
        applied twice (entry + exit).
    """
    if entry_price <= 0 or exit_price <= 0:
        raise ValueError("Prices must be positive")
    if side not in (1, -1):
        raise ValueError("side must be +1 (long) or -1 (short)")

    pnl = (exit_price - entry_price) / entry_price * 100.0 * side
    fee_pct = fee_rate * 2 * 100.0  # entrée + sortie
    return pnl - fee_pct



def calc_rsi(prices: Iterable[float], period: int = 14) -> float:
    """Compute the Relative Strength Index (RSI) using Wilder's smoothing.


    Parameters
    ----------
    prices:
        Ordered sequence of closing prices.
    period:
        Number of periods to use for the calculation. Must be positive and the
        length of ``prices`` must be at least ``period + 1``.
    """


    prices_list = [float(p) for p in prices]

    if period <= 0:
        raise ValueError("period must be positive")
    if len(prices_list) < period + 1:

        raise ValueError("len(prices) must be >= period + 1")

    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, period + 1):

        diff = prices_list[i] - prices_list[i - 1]

        if diff >= 0:
            gains.append(diff)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(-diff)

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period


    for i in range(period + 1, len(prices_list)):
        diff = prices_list[i] - prices_list[i - 1]

        gain = max(diff, 0.0)
        loss = max(-diff, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period


    if avg_gain == 0 and avg_loss == 0:
        return 50.0
    if avg_loss == 0:
        return 100.0
    if avg_gain == 0:
        return 0.0
>>>>>> main
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))



def calc_atr(highs: Iterable[float], lows: Iterable[float], closes: Iterable[float], period: int = 14) -> float:
    """Compute the Average True Range (ATR) using Wilder's smoothing.


    Parameters
    ----------
    highs, lows, closes:
        Ordered sequences of high, low and close prices. All sequences must
        have the same length and contain at least ``period + 1`` elements.
    period:
        Number of periods to use for the calculation. Must be positive.
    """


    highs_list = [float(h) for h in highs]
    lows_list = [float(l) for l in lows]
    closes_list = [float(c) for c in closes]

    length = len(highs_list)
    if length != len(lows_list) or length != len(closes_list):

        raise ValueError("Input sequences must have the same length")
    if period <= 0:
        raise ValueError("period must be positive")
    if length < period + 1:
        raise ValueError("Input sequences must have at least period + 1 elements")


    trs: list[float] = []
    for i in range(1, len(highs_list)):
        tr = max(
            highs_list[i] - lows_list[i],
            abs(highs_list[i] - closes_list[i - 1]),
            abs(lows_list[i] - closes_list[i - 1]),

        )
        trs.append(tr)

    atr = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    return atr


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

