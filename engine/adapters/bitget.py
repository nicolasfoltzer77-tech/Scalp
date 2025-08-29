import os
import requests
import time
import hmac
import hashlib

# ==============================
# CONFIG
# ==============================

BASE_URLS = {
    "spot": "https://api.bitget.com/api/spot/v1",
    "umcbl": "https://api.bitget.com/api/mix/v1",
    "cmcbl": "https://api.bitget.com/api/mix/v1",
}

MARKET_SUFFIX = {
    "spot": "_SPBL",
    "umcbl": "_UMCBL",
    "cmcbl": "_CMCBL",
}

# ==============================
# CLIENT
# ==============================

class BitgetClient:
    def __init__(self, market="umcbl"):
        self.api_key = os.getenv("BITGET_ACCESS_KEY")
        self.api_secret = os.getenv("BITGET_SECRET_KEY")
        self.passphrase = os.getenv("BITGET_PASSPHRASE")
        self.market = market.lower()

        if self.api_key is None or self.api_secret is None or self.passphrase is None:
            raise RuntimeError("⚠️ Missing Bitget API credentials in environment")

        if self.market not in BASE_URLS:
            raise ValueError(f"Unknown market type: {self.market}")

        self.base_url = BASE_URLS[self.market]

    # ------------------------------
    # Utility: sign request
    # ------------------------------
    def _sign(self, method, path, query=""):
        ts = str(int(time.time() * 1000))
        prehash = ts + method.upper() + path + query
        sign = hmac.new(
            self.api_secret.encode("utf-8"),
            prehash.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        sign_b64 = sign.hex()
        return ts, sign_b64

    # ------------------------------
    # Utility: make request
    # ------------------------------
    def _request(self, method, path, params=None):
        url = self.base_url + path
        query = ""
        if params:
            import urllib.parse
            query = "?" + urllib.parse.urlencode(params)

        ts, sign = self._sign(method, path, query)
        headers = {
            "ACCESS-KEY": self.api_key,
            "ACCESS-SIGN": sign,
            "ACCESS-TIMESTAMP": ts,
            "ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
        }

        resp = requests.request(method, url + query, headers=headers)
        if not resp.ok:
            raise RuntimeError(f"❌ API error {resp.status_code}: {resp.text}")
        return resp.json()

    # ------------------------------
    # Symbol resolution
    # ------------------------------
    def resolve_symbol(self, symbol: str) -> str:
        """Ajoute le suffixe attendu par Bitget (UMCBL, SPBL, etc)."""
        suffix = MARKET_SUFFIX.get(self.market, "")
        if symbol.endswith(suffix):
            return symbol
        return symbol + suffix

    # ------------------------------
    # Public endpoints
    # ------------------------------
    def fetch_ohlcv(self, symbol: str, timeframe="1m", limit=100):
        """Récupère OHLCV depuis Bitget."""
        s = self.resolve_symbol(symbol)

        # timeframe mapping
        tf_map = {
            "1m": "60",
            "5m": "300",
            "15m": "900",
            "1h": "3600",
            "4h": "14400",
            "1d": "86400",
        }
        if timeframe not in tf_map:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        if self.market == "spot":
            path = "/market/candles"
            params = {"symbol": s, "period": tf_map[timeframe], "limit": limit}
        else:  # umcbl, cmcbl
            path = "/market/candles"
            params = {"symbol": s, "granularity": tf_map[timeframe], "limit": limit}

        data = self._request("GET", path, params)
        if "data" not in data:
            raise RuntimeError(f"Unexpected API response: {data}")

        return data["data"]
