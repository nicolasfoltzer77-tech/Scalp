#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Base classes for strategies
"""

from __future__ import annotations
from typing import Dict, Any
import numpy as np
import pandas as pd

class Metrics:
    """Container for backtest metrics."""
    def __init__(self, pf: float, mdd: float, trades: int,
                 wr: float, sharpe: float):
        self.pf = pf
        self.mdd = mdd
        self.trades = trades
        self.wr = wr
        self.sharpe = sharpe

    @classmethod
    def from_trades(cls, pnl: np.ndarray) -> "Metrics":
        """Compute metrics from an array of trade PnLs."""
        if pnl is None or len(pnl) == 0:
            return cls(0.0, 1.0, 0, 0.0, 0.0)

        trades = len(pnl)
        wins = (pnl > 0).sum()
        losses = (pnl < 0).sum()

        wr = wins / trades if trades > 0 else 0.0
        gross_profit = pnl[pnl > 0].sum()
        gross_loss = -pnl[pnl < 0].sum()
        pf = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

        eq = pnl.cumsum()
        peak = np.maximum.accumulate(eq)
        dd = (peak - eq).max() if len(eq) > 0 else 0.0
        mdd = dd / (peak.max() + 1e-9) if peak.max() > 0 else 1.0

        sharpe = pnl.mean() / (pnl.std() + 1e-9) * np.sqrt(252) if trades > 1 else 0.0

        return cls(pf, mdd, trades, wr, sharpe)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pf": self.pf,
            "mdd": self.mdd,
            "trades": self.trades,
            "wr": self.wr,
            "sharpe": self.sharpe,
        }


class StrategyBase:
    """Base class for all strategies."""

    def __init__(self, params: Dict[str, Any]):
        self.params = params or {}

    def backtest(self, df: pd.DataFrame) -> Metrics:
        """Run backtest on OHLCV dataframe. Override in subclasses."""
        raise NotImplementedError

    def describe(self) -> Dict[str, Any]:
        return {"name": self.__class__.__name__, **self.params}