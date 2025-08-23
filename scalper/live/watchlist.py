# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
from typing import List


@dataclass
class WatchlistManager:
    symbols: List[str]

    @classmethod
    def from_env_or_default(cls) -> "WatchlistManager":
        # Tu peux lire une variable d'env ici si tu veux surcharger
        default = [
            "BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT",
            "DOGEUSDT","ADAUSDT","LTCUSDT","AVAXUSDT","LINKUSDT"
        ]
        return cls(default)