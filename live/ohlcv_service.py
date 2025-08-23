from __future__ import annotations
import time
from typing import Any, Dict, List, Optional

try:
    from scalp.adapters.market_data import MarketData
except Exception:
    MarketData = None  # type: ignore

class OhlcvService:
    """Lecture/normalisation OHLCV avec fallback agressifs."""
    def __init__(self, exchange) -> None:
        self.exchange = exchange
        self.md = MarketData(exchange) if MarketData is not None else None

    @staticmethod
    def normalize_rows(rows: Any) -> List[Dict[str, float]]:
        out: List[Dict[str, float]] = []
        if not rows: return out
        for r in rows:
            if isinstance(r, dict):
                ts = int(r.get("ts") or r.get("time") or r.get("timestamp") or 0)
                o = float(r.get("open", 0.0)); h = float(r.get("high", o)); l = float(r.get("low", o)); c = float(r.get("close", o))
                v = float(r.get("volume", r.get("vol", 0.0)))
            else:
                rr = list(r)
                if len(rr) >= 6 and isinstance(rr[0], (int, float)) and rr[0] > 10**10:
                    ts, o, h, l, c = int(rr[0]), float(rr[1]), float(rr[2]), float(rr[3]), float(rr[4]); v = float(rr[5])
                else:
                    o = float(rr[0]) if len(rr) > 0 else 0.0
                    h = float(rr[1]) if len(rr) > 1 else o
                    l = float(rr[2]) if len(rr) > 2 else o
                    c = float(rr[3]) if len(rr) > 3 else o
                    v = float(rr[4]) if len(rr) > 4 else 0.0
                    ts = int(rr[5]) if len(rr) > 5 else 0
            out.append({"ts": ts, "open": o, "high": h, "low": l, "close": c, "volume": v})
        return out

    async def fetch_once(self, symbol: str, interval: str = "1m", limit: int = 100) -> List[Dict[str, float]]:
        # 1) MarketData (si dispo)
        if self.md is not None:
            try:
                d = self.md.get_ohlcv(symbol, interval, limit)
                if isinstance(d, dict) and d.get("success") and d.get("data"):
                    return self.normalize_rows(d["data"])
            except Exception:
                pass

        # 2) Exchange natif
        rows: List[Any] = []
        try:
            data = self.exchange.get_kline(symbol, interval=interval)
        except Exception:
            data = None

        if isinstance(data, dict):
            rows = (
                data.get("data") or data.get("result") or data.get("records") or
                data.get("list") or data.get("items") or data.get("candles") or []
            )
            guard = 0
            while isinstance(rows, dict) and guard < 3:
                rows = (
                    rows.get("data") or rows.get("result") or rows.get("records") or
                    rows.get("list") or rows.get("items") or rows.get("candles") or rows.get("klines") or rows.get("bars") or []
                )
                guard += 1
        elif isinstance(data, (list, tuple)):
            rows = list(data)

        out = self.normalize_rows(rows)[-limit:]
        if out: return out

        # 3) Fallback strict via ticker -> bougie synthétique
        try:
            tkr = self.exchange.get_ticker(symbol)
            items = []
            if isinstance(tkr, dict): items = tkr.get("data") or tkr.get("result") or tkr.get("tickers") or []
            elif isinstance(tkr, (list, tuple)): items = list(tkr)
            if items:
                last = items[0]
                if isinstance(last, dict):
                    p = float(last.get("lastPrice", last.get("close", last.get("markPrice", 0.0))))
                    v = float(last.get("volume", last.get("usdtVolume", last.get("quoteVolume", 0.0))))
                else:
                    seq = list(last); p = float(seq[3] if len(seq) > 3 else seq[-2]); v = float(seq[4] if len(seq) > 4 else seq[-1])
                ts = int(time.time()*1000)
                return [{"ts": ts, "open": p, "high": p, "low": p, "close": p, "volume": v}]
        except Exception:
            pass
        return []