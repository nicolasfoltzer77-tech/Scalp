# scalper/live/fetcher.py
from __future__ import annotations
from typing import Dict, List, Optional

class DataFetcher:
    def __init__(self, client) -> None:
        self.client = client

    @staticmethod
    def _to_dict(rows: List[List[float]]) -> Dict[str, List[float]]:
        cols = ("timestamp","open","high","low","close","volume")
        out = {k: [] for k in cols}
        for r in rows:
            out["timestamp"].append(float(r[0]))
            out["open"].append(float(r[1]))
            out["high"].append(float(r[2]))
            out["low"].append(float(r[3]))
            out["close"].append(float(r[4]))
            out["volume"].append(float(r[5]))
        return out

    def fetch(self, symbol: str, timeframe: str, limit: int = 1500) -> Dict[str, List[float]]:
        rows = self.client.get_ohlcv(symbol=symbol, timeframe=timeframe, limit=limit)
        return self._to_dict(rows)

    def try_fetch_1h(self, symbol: str, limit: int = 1500) -> Optional[Dict[str, List[float]]]:
        try:
            rows = self.client.get_ohlcv(symbol=symbol, timeframe="1h", limit=limit)
            return self._to_dict(rows)
        except Exception:
            return None