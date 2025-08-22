from __future__ import annotations
from typing import Any, Dict, List, Optional, Sequence, Tuple
import time


def _to_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


class MarketData:
    """
    Adaptateur unique de données marché pour Bitget (ou autre exchange).
    Il encapsule:
      - get_ohlcv(symbol, interval, limit)
      - get_ticker(symbol)
    et normalise les retours en structures stables (dicts python simples).
    """

    def __init__(self, exchange) -> None:
        self.exchange = exchange

    # ---------- TICKER ----------
    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        raw = self.exchange.get_ticker(symbol)
        items: List[Dict[str, Any]] = []
        if isinstance(raw, dict):
            items = raw.get("data") or raw.get("result") or raw.get("tickers") or []
        elif isinstance(raw, (list, tuple)):
            # liste de dicts ou de listes -> on force dict
            for it in raw:
                if isinstance(it, dict):
                    items.append(it)
        if not items:
            return {"success": False, "data": []}
        d = items[0]
        last = _to_float(d.get("lastPrice", d.get("close", d.get("markPrice", 0.0))))
        bid = _to_float(d.get("bidPrice", d.get("bestBidPrice", d.get("buyOne", last))))
        ask = _to_float(d.get("askPrice", d.get("bestAskPrice", d.get("sellOne", last))))
        vol = _to_float(d.get("usdtVolume", d.get("quoteVolume", d.get("volume", 0.0))))
        return {
            "success": True,
            "data": [
                {
                    "symbol": symbol.replace("_", ""),
                    "last": last,
                    "bid": bid,
                    "ask": ask,
                    "volume": vol,
                }
            ],
        }

    # ---------- OHLCV ----------
    def get_ohlcv(
        self, symbol: str, interval: str = "1m", limit: int = 200
    ) -> Dict[str, Any]:
        """
        Normalise en: {"success": True, "data":[{"ts":ms,"open":...,"high":...,"low":...,"close":...,"volume":...}]}
        Supporte les retours:
          - dict {"data":[...]} ou {"result":[...]} ou imbriqués {"data":{"candles":[...]}}
          - list de dicts
          - list de listes [ts, o, h, l, c, v] ou [o,h,l,c,v,ts]
        """
        rows: List = []
        raw = None
        # Essayer API klines si disponible
        try:
            # tolérer param 'interval' ou 'granularity'
            raw = self.exchange.get_kline(symbol, interval=interval)
        except TypeError:
            try:
                raw = self.exchange.get_kline(symbol, granularity=interval)
            except Exception:
                raw = None
        except AttributeError:
            raw = None
        except Exception:
            raw = None

        if raw is not None:
            if isinstance(raw, dict):
                rows = (
                    raw.get("data")
                    or raw.get("result")
                    or raw.get("records")
                    or raw.get("list")
                    or raw.get("items")
                    or raw.get("candles")
                    or []
                )
                # déballer dict imbriqué
                guard = 0
                while isinstance(rows, dict) and guard < 3:
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
                    guard += 1
            elif isinstance(raw, (list, tuple)):
                rows = list(raw)

        out: List[Dict[str, Any]] = []
        if rows:
            seq = list(rows)
            for r in seq[-limit:]:
                if isinstance(r, dict):
                    ts = int(
                        r.get("ts")
                        or r.get("time")
                        or r.get("timestamp")
                        or 0
                    )
                    o = _to_float(r.get("open", 0))
                    h = _to_float(r.get("high", o))
                    l = _to_float(r.get("low", o))
                    c = _to_float(r.get("close", o))
                    v = _to_float(r.get("volume", r.get("vol", 0)))
                else:
                    rr = list(r)
                    # heuristique: si rr[0] ressemble à un ts (ms) -> [ts,o,h,l,c,v]
                    if len(rr) >= 6 and isinstance(rr[0], (int, float)) and rr[0] > 10 ** 10:
                        ts, o, h, l, c = int(rr[0]), _to_float(rr[1]), _to_float(rr[2]), _to_float(rr[3]), _to_float(rr[4])
                        v = _to_float(rr[5])
                    else:
                        # [o,h,l,c,v,ts] ou variantes courtes
                        o = _to_float(rr[0] if len(rr) > 0 else 0)
                        h = _to_float(rr[1] if len(rr) > 1 else o)
                        l = _to_float(rr[2] if len(rr) > 2 else o)
                        c = _to_float(rr[3] if len(rr) > 3 else o)
                        v = _to_float(rr[4] if len(rr) > 4 else 0)
                        ts = int(rr[5]) if len(rr) > 5 else int(time.time() * 1000)
                out.append({"ts": ts, "open": o, "high": h, "low": l, "close": c, "volume": v})
            return {"success": True, "data": out}

        # Fallback strict via ticker
        t = self.get_ticker(symbol)
        if not t.get("success") or not t.get("data"):
            return {"success": False, "data": []}
        last = t["data"][0]["last"]
        vol = t["data"][0]["volume"]
        ts = int(time.time() * 1000)
        return {
            "success": True,
            "data": [
                {
                    "ts": ts,
                    "open": last,
                    "high": last,
                    "low": last,
                    "close": last,
                    "volume": vol,
                }
            ],
        }
