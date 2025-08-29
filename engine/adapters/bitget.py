# -*- coding: utf-8 -*-
from __future__ import annotations

import time
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone

BASE = "https://api.bitget.com"

TF_SEC = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900,
    "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400
}

class BitgetError(RuntimeError):
    pass

class BitgetClient:
    def __init__(self, market="umcbl", timeout=15):
        self.market = market.lower()
        self.timeout = timeout

    def _ok(self, r: requests.Response):
        if r.status_code != 200:
            raise BitgetError(f"HTTP {r.status_code}: {r.text[:200]}")
        j = r.json()
        if str(j.get("code")) in ("00000", "0", "200"):
            return j
        raise BitgetError(f"API error {j}")

    def _sym(self, symbol: str) -> str:
        s = symbol.upper()
        if self.market == "umcbl" and not s.endswith("_UMCBL"):
            s += "_UMCBL"
        return s

    def fetch_ohlcv(self, symbol: str, timeframe="1m", limit=500):
        if timeframe not in TF_SEC:
            raise ValueError("timeframe non supporté")
        step = TF_SEC[timeframe] * 1000  # ms
        sym = self._sym(symbol)

        url = "/api/mix/v1/market/history-candles" if self.market == "umcbl" else "/api/spot/v1/market/candles"
        path = BASE + url

        end = int(time.time() * 1000)
        out = []
        while len(out) < limit:
            start = end - step * limit
            params = {
                "symbol": sym,
                "granularity": TF_SEC[timeframe],
                "startTime": start,
                "endTime": end,
                "limit": min(limit - len(out), 200)
            }
            r = requests.get(path, params=params, timeout=self.timeout)
            j = self._ok(r)
            data = j.get("data") or []
            if not data:
                break
            out.extend(data)
            end = int(data[-1][0]) - step
            if len(data) < 2:
                break
            time.sleep(0.1)

        return out[:limit]

    def fetch_ohlcv_df(self, symbol, timeframe="1m", limit=500):
        rows = self.fetch_ohlcv(symbol, timeframe, limit)
        df = pd.DataFrame(rows, columns=[
            "timestamp","open","high","low","close","volume","quote_volume"
        ])
        df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        for c in ["open","high","low","close","volume","quote_volume"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        return df.sort_values("timestamp").reset_index(drop=True)
