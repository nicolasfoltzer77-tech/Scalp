from __future__ import annotations
import os, time, hmac, hashlib, base64, json, requests
from typing import Any, Dict, Optional

class BitgetError(RuntimeError):
    """Erreur custom pour Bitget API."""
    pass


class BitgetBase:
    BASE = "https://api.bitget.com"

    def __init__(self, market: str = "umcbl", timeout: int = 12):
        self.market = market.lower()        # "umcbl" (futures USDT)
        self.timeout = timeout

    # -------------- utilitaires --------------
    @staticmethod
    def _ts() -> str:
        return str(int(time.time() * 1000))

    @staticmethod
    def _env(name: str, default: str = "") -> str:
        v = os.getenv(name, default)
        return v if v is not None else default

    def _sign(self, ts: str, method: str, path: str, body: str = "") -> str:
        secret = self._env("BITGET_SECRET_KEY")
        msg = f"{ts}{method}{path}{body}"
        mac = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).digest()
        return base64.b64encode(mac).decode()

    def _auth_headers(self, method: str, path: str, body: str = "") -> Dict[str, str]:
        ts = self._ts()
        return {
            "ACCESS-KEY": self._env("BITGET_ACCESS_KEY"),
            "ACCESS-PASSPHRASE": self._env("BITGET_PASSPHRASE"),
            "ACCESS-SIGN": self._sign(ts, method, path, body),
            "ACCESS-TIMESTAMP": ts,
            "Content-Type": "application/json",
            "locale": "en-US",
        }

    # -------------- HTTP --------------
    def _ok(self, r: requests.Response) -> Dict[str, Any]:
        if r.status_code != 200:
            raise BitgetError(f"HTTP {r.status_code}: {r.text[:300]}")
        js = r.json()
        code = str(js.get("code"))
        if code not in ("00000", "0", "200"):
            # l’API mix renvoie parfois directement un array pour certains endpoints publics,
            # dans ce cas on laisse le caller gérer.
            if not isinstance(js, list):
                raise BitgetError(f"Bitget error: {js}")
        return js

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None, auth: bool = False):
        url = f"{self.BASE}{path}"
        if auth:
            headers = self._auth_headers("GET", path, "")
            r = requests.get(url, params=params, headers=headers, timeout=self.timeout)
        else:
            r = requests.get(url, params=params, timeout=self.timeout)
        return self._ok(r)

    def _post(self, path: str, body: Dict[str, Any]):
        payload = json.dumps(body)
        headers = self._auth_headers("POST", path, payload)
        url = f"{self.BASE}{path}"
        r = requests.post(url, headers=headers, data=payload, timeout=self.timeout)
        return self._ok(r)

    # -------------- mapping TF --------------
    @staticmethod
    def tf_to_granularity(tf: str) -> str:
        """
        Bitget accepte pour /mix/market/candles des valeurs chaîne:
        '1m','3m','5m','15m','30m','1h','4h','12h','1d','1w'
        On renvoie tel quel si connu.
        """
        allowed = {"1m","3m","5m","15m","30m","1h","4h","12h","1d","1w"}
        tf = tf.strip().lower()
        if tf not in allowed:
            raise BitgetError(f"Unsupported timeframe '{tf}' for candles.")
        return tf
