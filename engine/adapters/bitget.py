import os
import requests

class BitgetClient:
    def __init__(self, market="umcbl"):
        self.base_url = "https://api.bitget.com"
        self.market = market  # "umcbl" pour Futures, "spbl" pour Spot

    def _request(self, method, path, params=None):
        url = f"{self.base_url}{path}"
        resp = requests.request(method, url, params=params)
        if not resp.ok:
            raise RuntimeError(f"❌ API error {resp.status_code}: {resp.text}")
        return resp.json()

    def fetch_ohlcv(self, symbol, timeframe="1m", limit=100):
        """
        symbol doit être du type BTCUSDT_UMCBL pour les Futures
        timeframe supportés : 1min, 5min, 15min, 1h, 4h, 1day
        """
        # map interne des timeframes vers API granularity
        tf_map = {
            "1m": "1min",
            "5m": "5min",
            "15m": "15min",
            "1h": "1hour",
            "4h": "4hour",
            "1d": "1day"
        }
        granularity = tf_map.get(timeframe, "1min")

        path = f"/api/mix/v1/market/candles"
        params = {
            "symbol": f"{symbol}_UMCBL",  # <--- correction clé !
            "granularity": granularity,
            "limit": limit
        }
        data = self._request("GET", path, params)
        return data
