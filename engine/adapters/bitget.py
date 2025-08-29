# -*- coding: utf-8 -*-
from __future__ import annotations

import time
import requests
import pandas as pd


BASE = "https://api.bitget.com"

# seconds par timeframe
TF_SEC = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "4h": 14400, "1d": 86400
}

SAFE_LIMIT = 200  # l'API v1 refuse souvent >200 => on reste raisonnable


class BitgetError(RuntimeError):
    pass


class BitgetClient:
    """
    Version minimaliste mais robuste :
    - pour futures UMCBL : /api/mix/v1/market/candles (granularity=int secondes)
    - fallback sur /api/mix/v1/market/history-candles si 400172 persiste
    - pour spot : /api/spot/v1/market/candles
    """
    def __init__(self, market: str = "umcbl", timeout: int = 15):
        self.market = market.lower()
        self.timeout = timeout

    # ------------ internals ------------
    def _ok(self, r: requests.Response) -> dict:
        if r.status_code != 200:
            raise BitgetError(f"HTTP {r.status_code}: {r.text[:200]}")
        j = r.json()
        code = str(j.get("code"))
        if code in ("00000", "0", "200") or j.get("status") in ("success", True):
            return j
        raise BitgetError(f"API error {code}: {j}")

    def _sym(self, symbol: str) -> str:
        s = symbol.upper()
        if self.market == "umcbl" and not s.endswith("_UMCBL"):
            s += "_UMCBL"
        return s

    # ------------ public ------------
    def fetch_ohlcv(self, symbol: str, timeframe: str = "1m", limit: int = 200):
        if timeframe not in TF_SEC:
            raise ValueError(f"timeframe non supporté: {timeframe}")
        gran = TF_SEC[timeframe]
        limit = max(1, min(int(limit), SAFE_LIMIT))
        sym = self._sym(symbol)

        # Ordre qui marche le mieux côté mix
        routes = (
            ["/api/mix/v1/market/candles", "/api/mix/v1/market/history-candles"]
            if self.market == "umcbl" else
            ["/api/spot/v1/market/candles", "/api/spot/v1/market/history-candles"]
        )

        last_err = None
        for path in routes:
            try:
                params = {"symbol": sym, "granularity": gran, "limit": limit}
                r = requests.get(BASE + path, params=params, timeout=self.timeout)
                j = self._ok(r)
                data = j.get("data") or j.get("result") or []
                if data:
                    return data
            except Exception as e:
                last_err = e
                time.sleep(0.05)
                continue

        raise BitgetError(f"Impossible d'obtenir OHLCV ({symbol} {timeframe}): {last_err}")

    def fetch_ohlcv_df(self, symbol: str, timeframe: str = "1m", limit: int = 200) -> pd.DataFrame:
        rows = self.fetch_ohlcv(symbol, timeframe, limit)
        # Normalisation 7 colonnes: ts, o, h, l, c, vol, quote_vol
        norm = []
        for r in rows:
            rr = list(r)[:7]
            while len(rr) < 7:
                rr.append(None)
            norm.append(rr)

        df = pd.DataFrame(norm, columns=[
            "timestamp", "open", "high", "low", "close", "volume", "quote_volume"
        ])
        for c in ("open", "high", "low", "close", "volume", "quote_volume"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.sort_values("timestamp", kind="stable").reset_index(drop=True)
        return df
