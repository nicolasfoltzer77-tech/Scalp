# scalper/exchange/bitget.py
from __future__ import annotations
import os
import requests
from typing import List, Dict, Any

BASE_URL = "https://api.bitget.com"

# Spot: period strings
_SPOT_PERIOD = {
    "1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min", "30m": "30min",
    "1h": "1hour", "4h": "4hour", "6h": "6hour", "12h": "12hour",
    "1d": "1day", "3d": "3day", "1w": "1week",
}
# Mix: granularity seconds
_MIX_GRAN = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "4h": 14400, "6h": 21600, "12h": 43200,
    "1d": 86400, "3d": 259200, "1w": 604800,
}

def _market_from_symbol(symbol: str) -> str:
    s = symbol.upper()
    if s.endswith("_SPBL"):
        return "spot"
    if s.endswith("_UMCBL"):
        return "umcbl"
    if s.endswith("_DMCBL"):
        return "dmcbl"
    if s.endswith("_CMCBL"):
        return "cmcbl"
    # fallback env / défaut umcbl
    return os.getenv("BITGET_MARKET", "umcbl").lower()

def _product_type(market: str) -> str:
    # valeur attendue par les endpoints mix (umcbl/dmcbl/cmcbl)
    if market in ("umcbl", "dmcbl", "cmcbl"):
        return market
    return "umcbl"

class BitgetExchange:
    """
    Wrapper simple: get_ohlcv(symbol, timeframe, limit) -> [[ts, o, h, l, c, v], ...]
    symbol spot ex: BTCUSDT_SPBL
    symbol perp ex: BTCUSDT_UMCBL / BTCUSD_DMCBL / BTCUSD_CMCBL
    """
    def __init__(self, api_key: str = "", api_secret: str = "", api_passphrase: str = "", timeout: int = 20) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "scalp-bot/1.0"})
        self.timeout = timeout

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = BASE_URL + path
        r = self.session.get(url, params=params, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        # Bitget: {"code":"00000","msg":"success","requestTime":..., "data":[...]}
        if not isinstance(data, dict) or str(data.get("code")) not in ("00000", "0", "200"):
            raise RuntimeError(f"Bitget error payload: {data}")
        return data

    def get_ohlcv(self, symbol: str, timeframe: str = "5m", limit: int = 500) -> List[List[float]]:
        timeframe = timeframe.lower()
        mkt = _market_from_symbol(symbol)

        if mkt == "spot":
            period = _SPOT_PERIOD.get(timeframe)
            if not period:
                raise ValueError(f"timeframe spot non supporté: {timeframe}")
            # Bitget spot: limit max souvent 1000
            lim = max(1, min(int(limit), 1000))
            params = {"symbol": symbol, "period": period, "limit": lim}
            data = self._get("/api/spot/v1/market/candles", params=params)
            rows = data.get("data") or []
            out: List[List[float]] = []
            # Bitget renvoie décroissant -> on inverse
            for r in reversed(rows):
                ts = int(r[0]); o, h, l, c = map(float, r[1:5]); v = float(r[5])
                out.append([ts, o, h, l, c, v])
            return out

        # MIX (umcbl/dmcbl/cmcbl)
        gran = _MIX_GRAN.get(timeframe)
        if not gran:
            raise ValueError(f"timeframe mix non supporté: {timeframe}")

        # Bitget mix: limit max souvent 200, granularity en secondes, productType parfois requis
        lim = max(1, min(int(limit), 200))
        params = {
            "symbol": symbol,
            "granularity": int(gran),
            "limit": lim,
            "productType": _product_type(mkt),
        }

        # essais: candles -> history-candles (certaines régions)
        try:
            data = self._get("/api/mix/v1/market/candles", params=params)
        except requests.HTTPError:
            data = self._get("/api/mix/v1/market/history-candles", params=params)

        rows = data.get("data") or []
        out: List[List[float]] = []
        for r in reversed(rows):
            ts = int(r[0]); o, h, l, c = map(float, r[1:5]); v = float(r[5])
            out.append([ts, o, h, l, c, v])
        return out