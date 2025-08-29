# -*- coding: utf-8 -*-
"""
Adaptateur Bitget très simple pour récupérer des bougies OHLCV.

- Futures (UMCBL) : /api/mix/v1/market/candles
    params: symbol = "<PAIR>_UMCBL", granularity=<sec>, limit=<n>

- Spot : /api/spot/v1/market/candles
    params: symbol = "<PAIR>", granularity=<sec>, limit=<n>

Aucune auth requise pour ces endpoints (public).
"""

from __future__ import annotations
import os
import time
import typing as T
import requests


MAP_TF_SEC = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}

class BitgetClient:
    def __init__(self, market: str = "umcbl", base_url: str | None = None, timeout: int = 15):
        """
        market:
          - 'umcbl' => futures USDT margined perpetual
          - 'spot'  => spot
        """
        self.market = market.lower()
        self.timeout = timeout
        if base_url:
            self.base_url = base_url.rstrip("/")
        else:
            self.base_url = "https://api.bitget.com"

        # routes
        self._route_mix_candles = "/api/mix/v1/market/candles"
        self._route_spot_candles = "/api/spot/v1/market/candles"

    # ---------------- internal helpers ---------------- #

    def _ok(self, resp: requests.Response) -> dict:
        if 200 <= resp.status_code < 300:
            try:
                return resp.json()
            except Exception:
                pass
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")

    def _request(self, method: str, path: str, params: dict) -> dict:
        url = self.base_url + path
        r = requests.request(method.upper(), url, params=params, timeout=self.timeout)
        js = self._ok(r)
        # Pour les endpoints public, la structure est {"code":"00000","data":[...]} / ou code différent
        code = js.get("code") or js.get("status") or ""
        if code not in ("00000", "success", 200, "200"):
            # Bitget renvoie 400172 etc si mauvais paramètre
            # On remonte l'erreur avec le payload pour debug
            raise RuntimeError(f"❌ API error {code}: {js}")
        return js

    # ---------------- public API ---------------- #

    def _symbol_for_market(self, pair: str) -> str:
        pair = pair.upper().replace("-", "")
        if self.market == "umcbl":
            # Futures perp USDT
            if not pair.endswith("_UMCBL"):
                pair = f"{pair}_UMCBL"
        return pair

    def _route_for_market(self) -> str:
        return self._route_mix_candles if self.market == "umcbl" else self._route_spot_candles

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 1000
    ) -> list[list[T.Union[str, float, int]]]:
        """
        Retour brut (liste de listes) tel que renvoyé par l’API Bitget :
        [timestamp_ms, open, high, low, close, volume, quote_volume?]
        Sur futures, Bitget renvoie 7 champs (incluant quote_volume).
        """
        tf_sec = MAP_TF_SEC.get(timeframe)
        if not tf_sec:
            raise ValueError(f"timeframe non supporté: {timeframe}")

        params = {
            "symbol": self._symbol_for_market(symbol),
            "granularity": tf_sec,
            "limit": max(1, min(int(limit), 1440)),  # Bitget limite à 1440
        }
        js = self._request("GET", self._route_for_market(), params)
        data = js.get("data") or []
        # Bitget renvoie généralement du +récent -> +ancien, ou l’inverse suivant l’endpoint.
        # On normalise en triant par timestamp croissant.
        try:
            data = sorted(data, key=lambda row: int(row[0]))
        except Exception:
            pass
        return data

    def fetch_ohlcv_df(
        self,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 1000
    ):
        import pandas as pd
        rows = self.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        if not rows:
            return pd.DataFrame(columns=["timestamp","open","high","low","close","volume","quote_volume","datetime"])
        # Bitget renvoie des chaînes -> cast
        df = pd.DataFrame(rows)
        # colonnes attendues (7 champs côté mix/umcbl)
        # 0: ts, 1: open, 2: high, 3: low, 4: close, 5: volume, 6: quote_volume (souvent)
        mapping = {
            0: "timestamp", 1: "open", 2: "high", 3: "low",
            4: "close", 5: "volume", 6: "quote_volume"
        }
        df = df.rename(columns=mapping)
        # force types
        for c in ("open","high","low","close","volume"):
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        if "quote_volume" in df.columns:
            df["quote_volume"] = pd.to_numeric(df["quote_volume"], errors="coerce")
        df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        cols = ["timestamp","open","high","low","close","volume","quote_volume","datetime"]
        return df[[c for c in cols if c in df.columns]]
