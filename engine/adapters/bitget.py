import os
import requests

MAP_TF = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}

class Client:
    def __init__(self, market="spbl", timeout=10):
        """
        market: "spbl" (spot) ou "umcbl" (USDT futures)
        """
        self.market = market
        self.timeout = timeout
        self.session = requests.Session()
        self.base_url = "https://api.bitget.com"

        # charge clés API si dispo (pas requis pour fetch public)
        self.api_key = os.getenv("BITGET_ACCESS_KEY")
        self.api_secret = os.getenv("BITGET_SECRET_KEY")
        self.passphrase = os.getenv("BITGET_PASSPHRASE")

    def fetch_ohlcv(self, symbol: str, timeframe="1m", limit=100):
        """
        Récupère des bougies OHLCV
        Retourne [[ts, open, high, low, close, vol], ...]
        """
        gran = MAP_TF.get(timeframe)
        if not gran:
            raise ValueError(f"Unsupported timeframe {timeframe}")

        sym = symbol.replace("/", "").upper()  # ex: BTCUSDT

        if self.market == "spbl":
            # Spot
            url = f"{self.base_url}/api/spot/v1/market/candles"
            params = {"symbol": sym, "granularity": str(gran), "limit": str(limit)}
        else:
            # Futures (UMCBL)
            url = f"{self.base_url}/api/mix/v1/market/candles"
            params = {
                "symbol": sym,
                "granularity": str(gran),
                "limit": str(limit),
                "productType": "umcbl",   # ✅ paramètre attendu
            }

        r = self.session.get(url, params=params, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()

        if "data" not in data:
            raise RuntimeError(f"Unexpected response: {data}")

        ohlcv = []
        for row in data["data"]:
            ts, open_, high, low, close, vol = row[:6]
            ohlcv.append([int(ts), float(open_), float(high),
                          float(low), float(close), float(vol)])
        return ohlcv
