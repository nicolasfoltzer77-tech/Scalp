import os
import time
import hmac
import hashlib
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


def _norm_symbol(symbol: str, market="umcbl") -> str:
    """
    Normalize symbol for Bitget API:
      - "BTCUSDT" or "BTC/USDT" + market="umcbl" => "BTCUSDT_UMCBL"
      - same with market="spbl" => "BTCUSDT_SPBL"
    """
    base = symbol.replace("/", "").upper()
    if market == "spbl":
        return f"{base}_SPBL"
    return f"{base}_UMCBL"


class Client:
    def __init__(self, api_key=None, api_secret=None, passphrase=None,
                 base_url="https://api.bitget.com", timeout=20, market="umcbl"):
        self.api_key = api_key or os.getenv("BITGET_ACCESS_KEY")
        self.api_secret = api_secret or os.getenv("BITGET_SECRET_KEY")
        self.passphrase = passphrase or os.getenv("BITGET_PASSPHRASE")
        self.base_url = base_url
        self.timeout = timeout
        self.market = market.lower()
        self.session = requests.Session()

    # ------------------------------------
    # Auth (si besoin pour les endpoints privés)
    # ------------------------------------
    def _sign(self, method, path, body=""):
        ts = str(int(time.time() * 1000))
        message = f"{ts}{method.upper()}{path}{body}"
        sign = hmac.new(self.api_secret.encode(), message.encode(), hashlib.sha256).hexdigest()
        return {
            "ACCESS-KEY": self.api_key,
            "ACCESS-SIGN": sign,
            "ACCESS-TIMESTAMP": ts,
            "ACCESS-PASSPHRASE": self.passphrase,
        }

    # ------------------------------------
    # Public API
    # ------------------------------------
    def fetch_ohlcv(self, symbol: str, timeframe="1m", limit=100):
        gran = MAP_TF.get(timeframe)
        if not gran:
            raise ValueError(f"Unsupported timeframe {timeframe}")

        # URL + params
        if self.market == "spbl":
            url = f"{self.base_url}/api/spot/v1/market/candles"
            sym = _norm_symbol(symbol, "spbl")
            params = {"symbol": sym, "granularity": str(gran), "limit": str(limit)}
        else:  # futures (UMCBL)
            url = f"{self.base_url}/api/mix/v1/market/candles"
            sym = _norm_symbol(symbol, "umcbl")
            params = {"symbol": sym, "granularity": str(gran), "limit": str(limit)}

        r = self.session.get(url, params=params, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()

        if "data" not in data:
            raise RuntimeError(f"Unexpected response: {data}")

        # Transform to list of [ts, open, high, low, close, volume]
        ohlcv = []
        for row in data["data"]:
            ts, open_, high, low, close, vol = row[:6]
            ohlcv.append([int(ts), float(open_), float(high),
                          float(low), float(close), float(vol)])
        return ohlcv
