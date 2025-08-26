#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import numpy as np
from dataclasses import dataclass
from typing import Dict, Any, Optional
from .base import StrategyBase, Metrics

class EmaAtrV1(StrategyBase):
    name = "ema_atr_v1"

    def __init__(self, params: Optional[Dict[str, Any]]=None):
        super().__init__(params or {
            "ema_fast": 12,
            "ema_slow": 34,
            "atr_period": 14,
            "lookahead_bars": 10
        })

    @staticmethod
    def _ema(a: np.ndarray, n: int) -> np.ndarray:
        alpha = 2.0/(n+1.0)
        out = np.empty_like(a); out[:] = np.nan
        prev = a[0]
        for i, x in enumerate(a):
            prev = alpha*x + (1-alpha)*prev
            out[i] = prev
        for i in range(1, n):
            out[i] = np.nan
        return out

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
        for i, sig in enumerate(longs, start=1):
            if sig and i+look < len(price):
                r = (price[i+look] - price[i]) / price[i]
                pnl.append(r); trades += 1
        for i, sig in enumerate(shorts, start=1):
            if sig and i+look < len(price):
                r = (price[i] - price[i+look]) / price[i]
                pnl.append(r); trades += 1

        if trades == 0:
            return Metrics(1.0, 0.5, 0, 0.0, 0.0)

        pnl = np.array(pnl)
        wins = (pnl > 0).sum()
        wr = wins / trades
        gain = pnl[pnl>0].sum()
        loss = -pnl[pnl<0].sum()
        pf = (gain / loss) if loss > 1e-12 else 2.0

        eq = (1.0 + pnl).cumprod()
        peak = np.maximum.accumulate(eq)
        dd = 1.0 - eq/peak
        mdd = float(np.nanmax(dd)) if len(dd) else 0.0

        sharpe = float(pnl.mean()/pnl.std()) if pnl.std() > 1e-12 else 0.0
        return Metrics(float(pf), float(mdd), int(trades), float(wr), float(sharpe))