from __future__ import annotations
from typing import List, Dict, Any

class MarketData:
    """Adapter de données de marché normalisées."""

    def __init__(self, exchange: Any):
        self.exchange = exchange

    def get_ohlcv(self, symbol: str, interval: str = "1m", limit: int = 100) -> Dict[str, List[Dict[str, float]]]:
        """Retourne une liste normalisée de bougies OHLCV."""
        try:
            data = self.exchange.get_kline(symbol, interval=interval)
        except Exception:
            data = None

        rows: List[Any] = []
        if data is not None:
            if isinstance(data, dict):
                rows = (
                    data.get("data")
                    or data.get("result")
                    or data.get("records")
                    or data.get("list")
                    or data.get("items")
                    or data.get("candles")
                    or []
                )
                depth_guard = 0
                while isinstance(rows, dict) and depth_guard < 3:
                    rows = (
                        rows.get("data")
                        or rows.get("result")
                        or rows.get("records")
                        or rows.get("list")
                        or rows.get("items")
                        or rows.get("candles")
                        or rows.get("klines")
                        or rows.get("bars")
                        or []
                    )
                    depth_guard += 1
            elif isinstance(data, (list, tuple)):
                rows = list(data)

        seq = list(rows) if isinstance(rows, (list, tuple)) else []
        out: List[Dict[str, float]] = []
        for r in seq[-limit:]:
            if isinstance(r, dict):
                t = int(r.get("ts") or r.get("time") or r.get("timestamp") or 0)
                o = float(r.get("open", 0.0))
                h = float(r.get("high", o))
                l = float(r.get("low", o))
                c = float(r.get("close", o))
                v = float(r.get("volume", r.get("vol", 0.0)))
            else:
                t = int(r[0]) if len(r) > 0 else 0
                o = float(r[1]) if len(r) > 1 else 0.0
                h = float(r[2]) if len(r) > 2 else o
                l = float(r[3]) if len(r) > 3 else o
                c = float(r[4]) if len(r) > 4 else o
                v = float(r[5]) if len(r) > 5 else 0.0
            out.append({"ts": t, "open": o, "high": h, "low": l, "close": c, "volume": v})
        return {"data": out}

    def get_ticker(self, symbol: str):
        """Délègue à l'exchange le ticker non normalisé."""
        return self.exchange.get_ticker(symbol)
