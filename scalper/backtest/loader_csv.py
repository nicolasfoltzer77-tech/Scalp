# scalper/backtest/loader_csv.py
from __future__ import annotations

import csv
from typing import Dict, List

from scalper.services.data_cache import csv_path

# Format de sortie : liste de bougies [ts, open, high, low, close, volume]
def load_ohlcv_csv(symbol: str, timeframe: str) -> List[List[float]]:
    path = csv_path(symbol, timeframe)
    rows: List[List[float]] = []
    with open(path, "r") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append([
                int(row["timestamp"]),
                float(row["open"]),
                float(row["high"]),
                float(row["low"]),
                float(row["close"]),
                float(row["volume"]),
            ])
    rows.sort(key=lambda x: x[0])
    return rows


def load_many(symbols: List[str], timeframe: str) -> Dict[str, List[List[float]]]:
    out: Dict[str, List[List[float]]] = {}
    for s in symbols:
        out[s] = load_ohlcv_csv(s, timeframe)
    return out