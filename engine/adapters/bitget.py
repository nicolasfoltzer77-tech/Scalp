# -*- coding: utf-8 -*-
from __future__ import annotations
import typing as T
import requests
import pandas as pd

MAP_TF_SEC = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "4h": 14400, "1d": 86400,
}

# limites "documentées" côté public -> on s'adapte si Bitget change d'avis
MAX_LIMIT = {"umcbl": 1000, "spot": 1000}

class BitgetClient:
    def __init__(self, market: str = "umcbl", base_url: str | None = None, timeout: int = 15):
        self.market = market.lower()
        self.base_url = (base_url or "https://api.bitget.com").rstrip("/")
        self.timeout = timeout
        self._route_mix_candles = "/api/mix/v1/market/candles"
        self._route_mix_hist   = "/api/mix/v1/market/history-candles"
        self._route_spot_candles = "/api/spot/v1/market/candles"

    # --------------- internals --------------- #
    def _ok(self, resp: requests.Response) -> dict:
        if 200 <= resp.status_code < 300:
            js = resp.json()
            code = str(js.get("code") or js.get("status") or "200")
            if code in ("00000", "success", "200", "0"):
                return js
            # en cas d'erreur API, on propage pour que le backoff s'applique
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

    # --------------- public --------------- #
    def fetch_ohlcv(self, symbol: str, timeframe: str = "1m", limit: int = 1000) -> list[list[T.Union[str, float, int]]]:
        tf_sec = MAP_TF_SEC.get(timeframe)
        if not tf_sec:
            raise ValueError(f"timeframe non supporté: {timeframe}")
        hard_cap = MAX_LIMIT.get(self.market, 1000)
        want = max(1, int(limit))
        # ordre d'essai pour UMCBL : candles -> history (puis backoff); pour spot : candles uniquement
        routes = []
        if self.market == "umcbl":
            routes = [self._route_mix_candles, self._route_mix_hist]
        else:
            routes = [self._route_spot_candles]

        sym = self._symbol_for_market(symbol)
        # backoff agressif si Bitget répond 400172 (params invalides: souvent limit trop grand)
        for trial_limit in [min(want, hard_cap), 500, 200, 100, 50]:
            for path in routes:
                params = {"symbol": sym, "granularity": tf_sec, "limit": trial_limit}
                try:
                    js = self._request(path, params)
                    data = js.get("data") or []
                    # data ordre desc chez bitget -> on trie asc
                    try:
                        data = sorted(data, key=lambda r: int(r[0]))
                    except Exception:
                        pass
                    if data:
                        return data
                except RuntimeError as e:
                    msg = str(e)
                    # si ce n'est PAS un "parameter verification failed" -> on tente l'autre route puis on remontera
                    if "400172" not in msg:
                        continue
                    # sinon, on passe au trial_limit suivant
                    continue
        # si rien n'a marché :
        raise RuntimeError(f"Bitget OHLCV indisponible pour {sym} {timeframe} (market={self.market})")

    def fetch_ohlcv_df(self, symbol: str, timeframe: str = "1m", limit: int = 1000) -> pd.DataFrame:
        rows = self.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        if not rows:
            return pd.DataFrame(columns=["timestamp","open","high","low","close","volume","quote_volume","datetime"])
        df = pd.DataFrame(rows).rename(columns={
            0:"timestamp",1:"open",2:"high",3:"low",4:"close",5:"volume",6:"quote_volume"
        })
        # cast
        for c in ("open","high","low","close","volume","quote_volume"):
            if c in df: df[c] = pd.to_numeric(df[c], errors="coerce")
        df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
        df["datetime"]  = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        cols = ["timestamp","open","high","low","close","volume","quote_volume","datetime"]
        return df[[c for c in cols if c in df.columns]]
