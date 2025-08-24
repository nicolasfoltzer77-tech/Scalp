# scalper/exchange/bitget.py
from __future__ import annotations
import os
import time
import math
import requests
from typing import List, Dict, Any, Optional

BASE_URL = "https://api.bitget.com"

# Mappings timeframe -> period/granularity
_SPOT_PERIOD = {
    "1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min", "30m": "30min",
    "1h": "1hour", "4h": "4hour", "6h": "6hour", "12h": "12hour",
    "1d": "1day", "3d": "3day", "1w": "1week"
}
_MIX_GRAN = {  # secondes
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "4h": 14400, "6h": 21600, "12h": 43200,
    "1d": 86400, "3d": 259200, "1w": 604800
}

def _detect_market(symbol: str) -> str:
    s = symbol.upper()
    if s.endswith("_SPBL"):
        return "spot"
    # contrats perp/coin margined (les trois suffixes vus chez Bitget)
    if s.endswith("_UMCBL") or s.endswith("_DMCBL") or s.endswith("_CMCBL"):
        return "mix"
    # fallback: variable d'env ou défaut umcbl
    return os.getenv("BITGET_MARKET", "mix")

class BitgetExchange:
    """
    Wrapper très simple pour lecture OHLCV (public).
    Signature compatible avec le code existant: get_ohlcv(symbol, timeframe, limit)
    - symbol Spot attendu: BTCUSDT_SPBL
    - symbol Perp USDT:    BTCUSDT_UMCBL
    - symbol Perp COIN:    BTCUSD_DMCBL / BTCUSD_CMCBL
    """
    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        api_passphrase: str = "",
        timeout: int = 20,
    ) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "scalp-bot/1.0"})
        self.timeout = timeout
        # (Clés gardées pour futures évolutions privées; ici on n’en a pas besoin pour OHLCV)

    # ---- HTTP helpers -------------------------------------------------------
    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = BASE_URL + path
        r = self.session.get(url, params=params, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, dict):
            raise ValueError(f"Réponse inattendue: {data}")
        # Bitget renvoie {"code":"00000","data":[...]}
        if str(data.get("code")) not in ("00000", "0", "200"):
            raise RuntimeError(f"Bitget error: {data}")
        return data

    # ---- Public market data -------------------------------------------------
    def get_ohlcv(self, symbol: str, timeframe: str = "5m", limit: int = 500) -> List[List[float]]:
        """
        Retourne une liste de bougies: [[ts, open, high, low, close, volume], ...]
        ts en millisecondes, trié croissant.
        """
        market = _detect_market(symbol)
        timeframe = timeframe.lower()
        if market == "spot":
            period = _SPOT_PERIOD.get(timeframe)
            if not period:
                raise ValueError(f"Timeframe spot non supporté: {timeframe}")
            # /api/spot/v1/market/candles  params: symbol, period, limit
            params = {"symbol": symbol, "period": period, "limit": int(limit)}
            data = self._get("/api/spot/v1/market/candles", params=params)
            rows = data.get("data") or []
            # Bitget renvoie en ordre décroissant; on renverse et convertit
            out: List[List[float]] = []
            for r in reversed(rows):
                # r = ["ts","open","high","low","close","volume"]
                ts = int(r[0])
                o, h, l, c = map(float, r[1:5])
                v = float(r[5])
                out.append([ts, o, h, l, c, v])
            return out

        # MIX (perp)
        gran = _MIX_GRAN.get(timeframe)
        if not gran:
            raise ValueError(f"Timeframe mix non supporté: {timeframe}")
        # /api/mix/v1/market/candles params: symbol, granularity, limit
        params = {"symbol": symbol, "granularity": int(gran), "limit": int(limit)}
        try:
            data = self._get("/api/mix/v1/market/candles", params=params)
        except requests.HTTPError as e:
            # Certains environnements n’acceptent que history-candles; fallback.
            data = self._get("/api/mix/v1/market/history-candles", params=params)
        rows = data.get("data") or []
        out: List[List[float]] = []
        for r in reversed(rows):
            # r = ["ts","open","high","low","close","volume", ...]
            ts = int(r[0])
            o, h, l, c = map(float, r[1:5])
            v = float(r[5])
            out.append([ts, o, h, l, c, v])
        return out