"""Simple backtesting helpers."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from scalp.bot_config import CONFIG
from scalp.metrics import calc_pnl_pct


def backtest_trades(
    trades: List[Dict[str, Any]],
    *,
    fee_rate: Optional[float] = None,
    zero_fee_pairs: Optional[List[str]] = None,
) -> float:
    """Compute cumulative PnL for a series of trades."""
    fee_rate = fee_rate if fee_rate is not None else CONFIG.get("FEE_RATE", 0.0)
    zero_fee = set(zero_fee_pairs or CONFIG.get("ZERO_FEE_PAIRS", []))

    pnl = 0.0
    for tr in trades:
        symbol = tr.get("symbol")
        entry = tr.get("entry")
        exit_ = tr.get("exit")
        side = tr.get("side", 1)
        if None in (symbol, entry, exit_):
            continue
        frate = 0.0 if symbol in zero_fee else fee_rate
        pnl += calc_pnl_pct(entry, exit_, side, frate)
    return pnl
