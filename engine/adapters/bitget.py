# Minimal Bitget OHLCV adapter (public candles)
# Compatible avec: from engine.adapters import bitget; bitget.Client(...).fetch_ohlcv(...)
import os, time, requests

# mapping timeframe -> seconds (Bitget "granularity")
MAP_TF = {
    "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "4h": 14400, "1d": 86400
}

def _granularity(tf: str) -> int:
    if tf not in MAP_TF:
        raise ValueError(f"Unsupported timeframe '{tf}' (supported: {sorted(MAP_TF)})")
    return MAP_TF[tf]

def _norm_symbol(symbol: str) -> str:
    # accepte "BTCUSDT" ou "BTC/USDT" -> "BTCUSDT"
    return symbol.replace("/", "").upper()

class Client:
    def __init__(self, api_key=None, api_secret=None, passphrase=None, base_url=None, session=None, timeout=20):
        self.api_key = api_key or os.getenv("BITGET_ACCESS_KEY", "")
        self.api_secret = api_secret or os.getenv("BITGET_SECRET_KEY", "")
        self.passphrase = passphrase or os.getenv("BITGET_PASSPHRASE", "")
        self.base_url = base_url or "https://api.bitget.com"
        self.s = session or requests.Session()
        self.timeout = timeout
        # (Les clés sont gardées pour évoluer vers du privé si besoin; non utilisées ici.)

    def fetch_ohlcv(self, symbol: str, timeframe: str = "1m", limit: int = 100):
        """
        Retourne une liste de bougies au format:
        [timestamp_ms, open, high, low, close, volume]
        Utilise l'endpoint spot public: /api/spot/v1/market/candles
        Docs: Bitget spot market candles.
        """
        sym = _norm_symbol(symbol)
        gran = _granularity(timeframe)
        url = f"{self.base_url}/api/spot/v1/market/candles"
        params = {
            "symbol": sym,
            "granularity": str(gran),
            "limit": str(limit)
        }
        r = self.s.get(url, params=params, timeout=self.timeout)
        r.raise_for_status()
        payload = r.json()
        data = payload.get("data", payload)

        # format Bitget: liste (newest first) de [ts, open, high, low, close, volume]
        ohlcv = []
        for row in reversed(data):
            ts = int(row[0])
            # certains renvoient en ms (13 digits). Normalise en ms:
            if ts < 2_000_000_000:   # si en secondes
                ts *= 1000
            ohlcv.append([
                ts,
                float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5])
            ])
        return ohlcv

# Helper facultatif
def fetch_ohlcv(symbol: str, timeframe: str = "1m", limit: int = 100):
    return Client().fetch_ohlcv(symbol, timeframe, limit)
