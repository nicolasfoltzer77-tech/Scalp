# -*- coding: utf-8 -*-
import requests
import pandas as pd

MAP_TF_SEC = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "4h": 14400, "1d": 86400,
}

MAX_LIMIT = {"umcbl": 200, "spot": 200}

class BitgetClient:
    def __init__(self, market="umcbl", base_url="https://api.bitget.com", timeout=15):
        self.market = market
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._route_mix = "/api/mix/v1/market/candles"
        self._route_spot = "/api/spot/v1/market/candles"

    def _ok(self, resp):
        if resp.status_code == 200:
            js = resp.json()
            if str(js.get("code")) in ("00000","0","200") or js.get("status")=="success":
                return js
            raise RuntimeError(f"API error {js}")
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")

    def fetch_ohlcv(self, symbol, timeframe="1m", limit=200):
        tf_sec = MAP_TF_SEC.get(timeframe)
        if not tf_sec:
            raise ValueError(f"Unsupported timeframe {timeframe}")

        if self.market == "umcbl":
            if not symbol.upper().endswith("_UMCBL"):
                symbol = f"{symbol.upper()}_UMCBL"
            route = self._route_mix
        else:
            route = self._route_spot

        limit = min(limit, MAX_LIMIT.get(self.market, 200))
        params = {"symbol": symbol, "granularity": tf_sec, "limit": limit}
        r = requests.get(self.base_url + route, params=params, timeout=self.timeout)
        js = self._ok(r)
        return js.get("data") or []

    def fetch_ohlcv_df(self, symbol, timeframe="1m", limit=200):
        rows = self.fetch_ohlcv(symbol, timeframe, limit)
        if not rows:
            return pd.DataFrame(columns=["timestamp","open","high","low","close","volume","quote_volume"])
        df = pd.DataFrame(rows).rename(columns={
            0:"timestamp",1:"open",2:"high",3:"low",4:"close",5:"volume",6:"quote_volume"
        })
        for c in ("open","high","low","close","volume","quote_volume"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        return df
