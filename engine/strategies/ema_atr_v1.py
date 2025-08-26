#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import numpy as np
from typing import Dict, Any, Optional
from .base import StrategyBase, Metrics


class EmaAtrV1(StrategyBase):
    """
    EMA/ATR v1 (simple, robuste, costs-aware).

    Logique:
      - Croisements EMA(fast) / EMA(slow) → signaux long/short.
      - PnL = variation de prix sur N barres ("lookahead_bars").
      - Coûts déduits sur chaque trade:
          * frais: 2 × fee_rate (entrée + sortie)
          * slippage: 2 × slippage_rate (entrée + sortie)
        où slippage_rate = slippage_bps / 10_000.

    Paramètres (self.params):
      ema_fast: int            (défaut: 12)
      ema_slow: int            (défaut: 34)
      lookahead_bars: int      (défaut: 10)

      # coûts / exécution
      taker_fee_rate: float    (défaut: 0.0008)   # 8 bps
      maker_fee_rate: float    (défaut: 0.0002)   # 2 bps
      prefer_maker: bool       (défaut: True)     # si True → utilise maker_fee_rate
      slippage_bps: float      (défaut: 5.0)      # 5 bps = 0.0005

    Remarques:
      - Cette version ne simule pas SL/TP en ATR; l'ATR est calculée à des fins futures.
      - Objectif: stabilité du pipeline + métriques réalistes (frais + slippage).
    """

    name = "ema_atr_v1"

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        super().__init__(
            params
            or {
                "ema_fast": 12,
                "ema_slow": 34,
                "lookahead_bars": 10,
                "taker_fee_rate": 0.0008,
                "maker_fee_rate": 0.0002,
                "prefer_maker": True,
                "slippage_bps": 5.0,
            }
        )

    # ------------------------- utils

    @staticmethod
    def _ema(a: np.ndarray, n: int) -> np.ndarray:
        alpha = 2.0 / (n + 1.0)
        out = np.empty_like(a)
        out[:] = np.nan
        prev = a[0]
        for i, x in enumerate(a):
            prev = alpha * x + (1 - alpha) * prev
            out[i] = prev
        # lissage initial pour éviter le warmup trop optimiste
        for i in range(1, n):
            out[i] = np.nan
        return out

    @staticmethod
    def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int) -> np.ndarray:
        """ATR de base pour un usage futur (non utilisé dans le PnL ici)."""
        tr = np.maximum.reduce(
            [
                high - low,
                np.abs(high[1:] - close[:-1]).tolist() + [np.nan],  # alignement simple
                np.abs(low[1:] - close[:-1]).tolist() + [np.nan],
            ]
        )
        atr = np.empty_like(tr)
        atr[:] = np.nan
        if len(tr) == 0 or n <= 1:
            return atr
        # EMA sur TR
        alpha = 2.0 / (n + 1.0)
        prev = tr[0]
        for i, x in enumerate(tr):
            prev = alpha * x + (1 - alpha) * prev
            atr[i] = prev
        # warmup
        for i in range(1, n):
            atr[i] = np.nan
        return atr

    def _total_cost_rate(self) -> float:
        """Coût proportionnel total entrée+sortie (frais + slippage)."""
        prefer_maker = bool(self.params.get("prefer_maker", True))
        maker_fee = float(self.params.get("maker_fee_rate", 0.0002))
        taker_fee = float(self.params.get("taker_fee_rate", 0.0008))
        fee = maker_fee if prefer_maker else taker_fee
        slip_bps = float(self.params.get("slippage_bps", 5.0))
        slip = slip_bps / 10000.0
        # entrée + sortie
        return 2.0 * fee + 2.0 * slip

    # ------------------------- coeur

    def backtest(self, df) -> Metrics:
        # garde-fous
        if df is None or len(df) < 200:
            return Metrics(1.0, 0.5, 0, 0.0, 0.0)

        price = df["close"].values.astype("float64")
        high = df["high"].values.astype("float64")
        low = df["low"].values.astype("float64")

        fast = int(self.params.get("ema_fast", 12))
        slow = int(self.params.get("ema_slow", 34))
        look = int(self.params.get("lookahead_bars", 10))

        # indicateurs
        ema_f = self._ema(price, fast)
        ema_s = self._ema(price, slow)
        # atr = self._atr(high, low, price, int(self.params.get("atr_period", 14)))  # prêt pour versions futures

        # signaux croisement
        longs = (ema_f[1:] >= ema_s[1:]) & (ema_f[:-1] < ema_s[:-1])
        shorts = (ema_f[1:] <= ema_s[1:]) & (ema_f[:-1] > ema_s[:-1])

        pnl = []
        trades = 0
        cost = self._total_cost_rate()

        # longs: r = (P_exit - P_entry) / P_entry
        for i, sig in enumerate(longs, start=1):
            if sig and i + look < len(price):
                r = (price[i + look] - price[i]) / price[i]
                r_net = r - cost
                pnl.append(r_net)
                trades += 1

        # shorts: r = (P_entry - P_exit) / P_entry
        for i, sig in enumerate(shorts, start=1):
            if sig and i + look < len(price):
                r = (price[i] - price[i + look]) / price[i]
                r_net = r - cost
                pnl.append(r_net)
                trades += 1

        if trades == 0:
            return Metrics(1.0, 0.5, 0, 0.0, 0.0)

        pnl = np.array(pnl, dtype="float64")

        # métriques
        wins = (pnl > 0).sum()
        wr = float(wins) / float(trades)
        gain = pnl[pnl > 0].sum()
        loss = -pnl[pnl < 0].sum()
        pf = (gain / loss) if loss > 1e-12 else float("inf")
        if not np.isfinite(pf):
            pf = 2.0  # borne haute pour éviter l'infini en cas d'aucune perte

        # equity & MDD
        eq = (1.0 + pnl).cumprod()
        peak = np.maximum.accumulate(eq)
        dd = 1.0 - eq / peak
        mdd = float(np.nanmax(dd)) if len(dd) else 0.0

        # Sharpe simplifié (bar-return), pas annualisé
        std = pnl.std()
        sharpe = float(pnl.mean() / std) if std > 1e-12 else 0.0

        return Metrics(float(pf), float(mdd), int(trades), float(wr), float(sharpe))