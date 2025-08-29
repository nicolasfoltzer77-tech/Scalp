import os
import requests


MAP_TF = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}


class BitgetClient:
    BASE_URLS = {
        "spot": "https://api.bitget.com/api/spot/v1",
        "umcbl": "https://api.bitget.com/api/mix/v1",
        "cmcbl": "https://api.bitget.com/api/mix/v1",
    }

    def __init__(self, market="umcbl"):
        self.market = market
        if market not in self.BASE_URLS:
            raise ValueError(f"Market non supporté: {market}")
        self.base = self.BASE_URLS[market]

    def _request(self, method, path, params=None):
        url = f"{self.base}{path}"
        resp = requests.request(method, url, params=params)
        if not resp.ok:
            raise RuntimeError(f"❌ API error {resp.status_code}: {resp.text}")
        return resp.json()

    def fetch_ohlcv(self, symbol, timeframe="1m", limit=100):
        if timeframe not in MAP_TF:
            raise ValueError(f"Timeframe non supporté: {timeframe}")

        granularity = MAP_TF[timeframe]

        if self.market == "spot":
            path = "/market/candles"
            params = {"symbol": symbol, "granularity": granularity, "limit": limit}

        elif self.market == "umcbl":
            path = "/market/candles"
            # ⚡ ici on force BTCUSDT → BTCUSDT_UMCBL
            if not symbol.endswith("_UMCBL"):
                symbol = f"{symbol}_UMCBL"
            params = {"symbol": symbol, "granularity": granularity, "limit": limit}

        else:
            raise NotImplementedError(f"fetch_ohlcv non dispo pour {self.market}")

        data = self._request("GET", path, params=params)

        if "data" not in data:
            raise RuntimeError(f"Réponse invalide: {data}")

        # Convertir data → [ts, o, h, l, c, v]
        result = []
        for row in data["data"]:
            # Futures renvoient : [timestamp, open, high, low, close, volume]
            ts = int(row[0])
            o, h, l, c, v = map(float, row[1:6])
            result.append([ts, o, h, l, c, v])

        return result
