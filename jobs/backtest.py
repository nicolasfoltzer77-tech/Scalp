#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import numpy as np
from typing import Dict, Any, Optional
from .base import StrategyBase, Metrics


class EmaAtrV1(StrategyBase):
    """
    EMA/ATR v1 (simple, costs-aware)
    - Signaux: croisement EMA(fast)/EMA(slow)
    - PnL: variation sur N barres (lookahead_bars)
    - Coûts par trade: 2*(fee) + 2*(slippage_bps/10_000)
    """

    name = "ema_atr_v1"

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        super().__init__(
            params or {
                "ema_fast": 12,
                "ema_slow": 34,
                "lookahead_bars": 10,
                "taker_fee_rate": 0.0008,
                "maker_fee_rate": 0.0002,
                "prefer_maker": True,
                "slippage_bps": 5.0,
            }
        )

    @staticmethod
    def _ema(a: np.ndarray, n: int) -> np.ndarray:
        alpha = 2.0 / (n + 1.0)
        out = np.empty_like(a); out[:] = np.nan
        prev = a[0]
        for i, x in enumerate(a):
            prev = alpha * x + (1 - alpha) * prev
            out[i] = prev
        for i in range(1, n):
            out[i] = np.nan
        return out

    def _total_cost_rate(self) -> float:
        prefer_maker = bool(self.params.get("prefer_maker", True))
        maker_fee = float(self.params.get("maker_fee_rate", 0.0002))
        taker_fee = float(self.params.get("taker_fee_rate", 0.0008))
        fee = maker_fee if prefer_maker else taker_fee
        slip = float(self.params.get("slippage_bps", 5.0)) / 10000.0
        return 2.0 * fee + 2.0 * slip

    def backtest(self, df) -> Metrics:
        if df is None or len(df) < 200:
            return Metrics(1.0, 0.5, 0, 0.0, 0.0)

        price = df["close"].values.astype("float64")
        fast = int(self.params.get("ema_fast", 12))
        slow = int(self.params.get("ema_slow", 34))
        look = int(self.params.get("lookahead_bars", 10))

        ema_f = self._ema(price, fast)
        ema_s = self._ema(price, slow)

        longs  = (ema_f[1:] >= ema_s[1:]) & (ema_f[:-1] < ema_s[:-1])
        shorts = (ema_f[1:] <= ema_s[1:]) & (ema_f[:-1] > ema_s[:-1])

        pnl = []
        trades = 0
        cost = self._total_cost_rate()

        for i, sig in enumerate(longs, start=1):
            if sig and i + look < len(price):
                r = (price[i + look] - price[i]) / price[i]
                pnl.append(r - cost); trades += 1

        for i, sig in enumerate(shorts, start=1):
            if sig and i + look < len(price):
                r = (price[i] - price[i + look]) / price[i]
                pnl.append(r - cost); trades += 1

        if trades == 0:
            return Metrics(1.0, 0.5, 0, 0.0, 0.0)

        pnl = np.array(pnl, dtype="float64")
        wins = (pnl > 0).sum()
        wr = float(wins) / float(trades)
        gain = pnl[pnl > 0].sum()
        loss = -pnl[pnl < 0].sum()
        pf = (gain / loss) if loss > 1e-12 else 2.0

        eq = (1.0 + pnl).cumprod()
        peak = np.maximum.accumulate(eq)
        dd = 1.0 - eq / peak
        mdd = float(np.nanmax(dd)) if len(dd) else 0.0

        std = pnl.std()
        sharpe = float(pnl.mean() / std) if std > 1e-12 else 0.0

        return Metrics(float(pf), float(mdd), int(trades), float(wr), float(sharpe))