from __future__ import annotations
import os, time, hmac, hashlib, base64, json, requests

class BitgetError(RuntimeError):
    """Erreur custom pour Bitget API"""
    pass


class BitgetClient:
    BASE = "https://api.bitget.com"

    def __init__(self, market: str = "umcbl"):
        self.market = market.lower()

    # ------------------------
    # Utils internes
    # ------------------------
    def _ts(self) -> str:
        """timestamp ms string"""
        return str(int(time.time() * 1000))

    def _sign(self, ts: str, method: str, path: str, body: str = "") -> str:
        secret = os.getenv("BITGET_SECRET_KEY", "")
        msg = f"{ts}{method}{path}{body}"
        mac = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).digest()
        return base64.b64encode(mac).decode()

    def _auth_headers(self, method: str, path: str, body: str = "") -> dict:
        ts = self._ts()
        return {
            "ACCESS-KEY": os.getenv("BITGET_ACCESS_KEY", ""),
            "ACCESS-PASSPHRASE": os.getenv("BITGET_PASSPHRASE", ""),
            "ACCESS-SIGN": self._sign(ts, method, path, body),
            "ACCESS-TIMESTAMP": ts,
            "Content-Type": "application/json",
            "locale": "en-US",
        }

    # ------------------------
    # Public OHLCV
    # ------------------------
    def fetch_ohlcv(self, symbol: str, tf: str = "1m", limit: int = 200):
        """
        Récupère les chandelles OHLCV publiques
        symbol: "BTCUSDT"
        tf: "1m", "5m", "1h" ...
        return: list[[ts,open,high,low,close,volume,quote_volume]]
        """
        path = "/api/mix/v1/market/candles"
        url  = f"{self.BASE}{path}"
        params = {
            "symbol": f"{symbol}_{self.market.upper()}",
            "granularity": tf,
            "limit": str(limit)
        }
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            raise BitgetError(f"HTTP {r.status_code}: {r.text[:200]}")
        js = r.json()
        if str(js.get("code")) not in ("00000", "0", "200"):
            raise BitgetError(f"fetch_ohlcv error: {js}")
        data = js.get("data") or []
        # Bitget retourne newest->oldest, on inverse
        data = list(reversed(data))
        out = []
        for row in data:
            ts, open_, high, low, close, vol = row[:6]
            out.append([
                int(ts),
                float(open_), float(high), float(low), float(close),
                float(vol),  # volume
                None         # pas toujours fourni : quote_volume
            ])
        return out

    # ------------------------
    # Trading (PRIVATE)
    # ------------------------
    def place_order(self, symbol: str, side: str, size: float):
        """
        Place un ordre marché sur UMCBL (futures linéaires USDT)
        side: 'open_long' ou 'close_long'
        """
        dry = os.getenv("DRY_RUN", "true").lower() in ("1","true","yes","on")
        if dry:
            return f"DRY-{int(time.time())}"

        path = "/api/mix/v1/order/placeOrder"
        url  = self.BASE + path
        body = {
            "symbol": f"{symbol}_{self.market.upper()}",
            "productType": self.market,
            "marginCoin": "USDT",
            "size": str(size),
            "side": side,               # open_long / close_long
            "orderType": "market",
            "timeInForceValue": "normal"
        }
        payload = json.dumps(body)
        headers = self._auth_headers("POST", path, payload)
        r = requests.post(url, headers=headers, data=payload, timeout=10)
        if r.status_code != 200:
            raise BitgetError(f"HTTP {r.status_code}: {r.text[:200]}")
        js = r.json()
        if str(js.get("code")) not in ("00000","0","200"):
            raise BitgetError(f"Bitget placeOrder error: {js}")
        return js.get("data", {}).get("orderId") or js.get("data")
