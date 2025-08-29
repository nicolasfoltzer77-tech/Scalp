# engine/adapters/bitget.py
# Client Bitget simple: essaie v2 d'abord, retombe sur v1 si besoin.
from __future__ import annotations

import os
import time
import typing as T
import requests

# --- Maps timeframe -> granularity ---
# v2 accepte '1m','5m','15m','1h','4h','1d'
# v1 attend des secondes: 60,300,900,3600,14400,86400
V2_GRAN = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "4h": "4h",
    "6h": "6h",
    "8h": "8h",
    "12h": "12h",
    "1d": "1d",
}
V1_GRAN = {
    "1m": "60",
    "3m": str(3 * 60),
    "5m": str(5 * 60),
    "15m": str(15 * 60),
    "30m": str(30 * 60),
    "1h": str(60 * 60),
    "4h": str(4 * 60 * 60),
    "6h": str(6 * 60 * 60),
    "8h": str(8 * 60 * 60),
    "12h": str(12 * 60 * 60),
    "1d": str(24 * 60 * 60),
}

def _tf_v2(tf: str) -> str:
    if tf not in V2_GRAN:
        raise ValueError(f"Unsupported timeframe for v2: {tf}")
    return V2_GRAN[tf]

def _tf_v1(tf: str) -> str:
    if tf not in V1_GRAN:
        raise ValueError(f"Unsupported timeframe for v1: {tf}")
    return V1_GRAN[tf]


class BitgetClient:
    """
    market:
      - 'umcbl' (USDT-M futures)  -> mix endpoints
      - 'cmcbl' (USDC-M futures) -> mix endpoints
      - 'spbl'  (spot)           -> spot endpoints
    Par défaut: umcbl (tes trades futur USDT-M).
    """

    def __init__(self, market: str = "umcbl", base_url: str = "https://api.bitget.com"):
        self.market = market.lower()
        self.base_url = base_url.rstrip("/")

        # Clés éventuelles (pas nécessaires pour les bougies publiques)
        self.access_key = os.getenv("BITGET_ACCESS_KEY") or os.getenv("BITGET_API_KEY")
        self.secret_key = os.getenv("BITGET_SECRET_KEY") or os.getenv("BITGET_API_SECRET")
        self.passphrase = os.getenv("BITGET_PASSPHRASE") or os.getenv("BITGET_PASS_PHRASE")

        # simple UA pour éviter certains 403
        self.headers = {
            "User-Agent": "scalp-backtest/1.0",
            "Accept": "application/json",
        }

    # ---------- HTTP helpers ----------
    def _get(self, path: str, params: dict, timeout: int = 15) -> requests.Response:
        url = f"{self.base_url}{path}"
        r = requests.get(url, params=params, headers=self.headers, timeout=timeout)
        return r

    @staticmethod
    def _ok(resp: requests.Response) -> dict:
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")
        # Bitget retourne {"code":"00000","data":[...],...} en v2
        # ou {"code":"00000","data":[...]} en v1; sinon message/erreur.
        js = resp.json()
        code = str(js.get("code", ""))
        if code != "00000":
            raise RuntimeError(f"❌ API error {resp.status_code}: {resp.text}")
        return js

    # ---------- Public OHLCV ----------
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 1000,
    ) -> T.List[T.List[T.Union[int, float, str]]]:
        """
        Retourne une liste de lignes OHLCV (timestamp_ms, open, high, low, close, volume)
        Essaie v2 en premier; si 4xx -> fallback v1.
        """

        # Normalisation symboles selon market
        m = self.market
        if m in ("umcbl", "cmcbl"):  # futures (mix)
            # v2 mix: symbol = "BTCUSDT", productType="umcbl"
            sym_v2 = symbol.replace("_UMCBL", "").replace("_CMCBL", "").replace("_SPBL", "")
            params_v2 = {
                "symbol": sym_v2,
                "productType": m,
                "granularity": _tf_v2(timeframe),
                "limit": str(min(max(limit, 1), 1000)),
            }
            path_v2 = "/api/v2/mix/market/candles"

            # v1 mix: symbol = "BTCUSDT_UMCBL" (ou _CMCBL) + granularity en secondes
            sym_v1 = f"{sym_v2}_{m.upper()}"
            params_v1 = {
                "symbol": sym_v1,
                "granularity": _tf_v1(timeframe),  # string exigée
                "limit": str(min(max(limit, 1), 1000)),
            }
            path_v1 = "/api/mix/v1/market/candles"

        elif m == "spbl":  # spot
            # v2 spot: symbol = "BTCUSDT"
            sym_v2 = symbol.replace("_SPBL", "")
            params_v2 = {
                "symbol": sym_v2,
                "granularity": _tf_v2(timeframe),
                "limit": str(min(max(limit, 1), 1000)),
            }
            path_v2 = "/api/v2/spot/market/candles"

            # v1 spot: symbol = "BTCUSDT_SPBL" + seconds
            sym_v1 = f"{sym_v2}_SPBL"
            params_v1 = {
                "symbol": sym_v1,
                "granularity": _tf_v1(timeframe),
                "limit": str(min(max(limit, 1), 1000)),
            }
            path_v1 = "/api/spot/v1/market/candles"
        else:
            raise ValueError(f"Unknown market: {self.market}")

        # --- Try v2 ---
        r2 = self._get(path_v2, params_v2)
        if r2.status_code == 200:
            data = self._ok(r2).get("data", [])
            return data

        # --- Fallback v1 (souvent 400172 si mauvais format) ---
        r1 = self._get(path_v1, params_v1)
        data = self._ok(r1).get("data", [])
        return data
