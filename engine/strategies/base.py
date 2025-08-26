#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass
class Metrics:
    pf: float
    mdd: float
    trades: int
    wr: float
    sharpe: float

class StrategyBase:
    """
    Interface minimale pour plug-in stratégie.
    """
    name: str = "base"

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        self.params = params or {}

    def backtest(self, df) -> Metrics:
        """
        Reçoit un DataFrame OHLCV (timestamp, open, high, low, close, volume)
        et renvoie des Metrics.
        """
        raise NotImplementedError

    def describe(self) -> Dict[str, Any]:
        """Retourne les paramètres utiles (pour logs/exp tracking)."""
        return {"name": self.name, **self.params}