# -*- coding: utf-8 -*-
from __future__ import annotations
import typing as T
import requests
import pandas as pd
import time

MAP_TF_SEC = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "4h": 14400, "1d": 86400,
}

MAX_LIMIT = {"umcbl": 200, "spot": 200}  # hard cap observé

class BitgetClient:
    def __init__(self, market: str = "umcbl", base_url: str | None = None, timeout: int = 15):
        self.market = market.lower()
        self.base_url = (base_url or "https://api.bitget.com").rstrip("/")
        self.timeout = timeout
        self._route_mix_candles = "/api/mix/v1/market/candles"
        self._route_mix_hist   = "/api/mix/v1/market/history-candles"
        self._route_spot_candles = "/api/spot/v1/market/candles"

    def _ok(self, resp: requests.Response) -> dict:
        if 200 <= resp.status_code < 300:
            js = resp.json()
            code = str(js.get("code") or js.get("status") or "200")
            if code in ("00000", "success", "200", "0"):
                return js
            raise RuntimeError(f"{code}:{js.get('msg','')}|{resp.status_code}")
        raise RuntimeError(f"HTTP{resp.status_code}:{resp.text[:180]}")

    def _request(self, path: str, params: dict) -> dict:
        url = self.base_url + path
        r = requests.get(url, params=params, timeout=self.timeout)
        return self._ok(r)

    def _symbol_for_market(self, pair: str) -> str:
        p = pair.upper().replace("-", "")
        if self.market == "umcbl" and not p.endswith("_UMCBL"):
            p = f"{p}_UMCBL"
        return p

    def fetch_ohlcv(self, symbol: str, timeframe: str = "1m", limit: int = 1000) -> list[list[T.Union[str, float, int]]]:
        tf_sec = MAP_TF_SEC.get(timeframe)
        if not tf_sec:
            raise ValueError(f"timeframe non supporté: {timeframe}")

        sym = self._symbol_for_market(symbol)
        routes = [self._route_mix_candles, self._route_mix_hist] if self.market == "umcbl" else [self._route_spot_candles]

        # segmentation automatique
        chunk_size = MAX_LIMIT.get(self.market, 200)
        all_rows: list = []
        remaining = limit
        cursor = None  # timestamp de départ

        while remaining > 0:
            batch = min(chunk_size, remaining)
            for path in routes:
                params = {"symbol": sym, "granularity": tf_sec, "limit": batch}
                if cursor:
                    params["endTime"] = cursor
                try:
                    js = self._request(path, params)
                    rows = js.get("data") or []
                    if not rows:
                        remaining = 0
                        break
                    rows = sorted(rows, key=lambda r: int(r[0]))
                    all_rows.extend(rows)
                    cursor = int(rows[0][0]) - tf_sec * 1000
                    remaining -= len(rows)
                    time.sleep(0.2)  # anti-rate-limit
                    break
                except Exception as e:
                    continue
            else:
                break

        return all_rows

    def fetch_ohlcv_df(self, symbol: str, timeframe: str = "1m", limit: int = 1000) -> pd.DataFrame:
        rows = self.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        if not rows:
            return pd.DataFrame(columns=["timestamp","open","high","low","close","volume","quote_volume","datetime"])
        df = pd.DataFrame(rows).rename(columns={
            0:"timestamp",1:"open",2:"high",3:"low",4:"close",5:"volume",6:"quote_volume"
        })
        for c in ("open","high","low","close","volume","quote_volume"):
            if c in df: df[c] = pd.to_numeric(df[c], errors="coerce")
        df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
        df["datetime"]  = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        return df
