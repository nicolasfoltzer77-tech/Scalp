"""Simple backtesting helpers."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from scalp.bot_config import CONFIG
from scalp.metrics import calc_pnl_pct
from .walkforward import walk_forward

__all__ = ["backtest_trades", "walk_forward_windows", "walk_forward"]


def _apply_slippage(price: float, side: int, bps: float, *, is_entry: bool) -> float:
    """Return price adjusted for slippage in basis points.

    ``side`` is ``1`` for long entries and ``-1`` for shorts.  ``is_entry``
    indicates whether the adjustment is for the entry or the exit leg.
    """

    slip = bps / 10000.0
    if side == 1:
        return price * (1 + slip) if is_entry else price * (1 - slip)
    return price * (1 - slip) if is_entry else price * (1 + slip)


def backtest_trades(
    trades: List[Dict[str, Any]],
    *,
    fee_rate: Optional[float] = None,
    slippage_bps: float = 0.0,
    logger: Any | None = None,
) -> float:
    """Compute cumulative PnL for a series of trades.

    ``slippage_bps`` simulates execution slippage for both entry and exit.
    If ``logger`` is provided it must expose a ``log(dict)`` method and each
    trade will be recorded with the computed PnL using the executed prices.
    """
    fee_rate = fee_rate if fee_rate is not None else CONFIG.get("FEE_RATE", 0.0)

    pnl = 0.0
    for tr in trades:
        symbol = tr.get("symbol")
        entry = tr.get("entry")
        exit_ = tr.get("exit")
        side = tr.get("side", 1)
        if None in (symbol, entry, exit_):
            continue
        entry_exec = _apply_slippage(float(entry), side, slippage_bps, is_entry=True)
        exit_exec = _apply_slippage(float(exit_), -side, slippage_bps, is_entry=False)
        pnl_trade = calc_pnl_pct(entry_exec, exit_exec, side, fee_rate)
        if logger is not None:
            logger.log(
                {
                    "pair": symbol,
                    "tf": tr.get("tf"),
                    "dir": "long" if side > 0 else "short",
                    "entry": entry_exec,
                    "sl": tr.get("sl"),
                    "tp": tr.get("tp"),
                    "score": tr.get("score"),
                    "reasons": tr.get("reasons"),
                    "pnl": pnl_trade,
                }
            )
        pnl += pnl_trade
    return pnl


def walk_forward_windows(series: List[Any], train: int, test: int):
    """Yield sequential ``(train, test)`` windows for walk-forward analysis.

    Parameters
    ----------
    series:
        Ordered data sequence.  The function simply slices the input and does
        not inspect the values.
    train, test:
        Number of elements for the training and testing windows respectively.
    """

    end = len(series) - train - test + 1
    step = test if test > 0 else 1
    for start in range(0, max(0, end), step):
        train_slice = series[start : start + train]
        test_slice = series[start + train : start + train + test]
        if len(test_slice) < test or len(train_slice) < train:
            break
        yield train_slice, test_slice
