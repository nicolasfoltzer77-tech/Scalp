from __future__ import annotations
import os, time, requests
from typing import Any, Dict, Optional, Union

class BitgetError(RuntimeError):
    pass

class BitgetBase:
    """
    Base HTTP pour les endpoints publics Bitget.
    - Support dict (code/data/…) ET list (candles).
    - timeouts + retries simples.
    """
    BASE = "https://api.bitget.com"
    TIMEOUT = 10
    RETRIES = 2

    def __init__(self, market: str = "umcbl"):
        self.market = market.lower()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "scalp-bot/1.0"})

    # ---------- HTTP ----------
    def _ok(self, r: requests.Response) -> Union[Dict[str, Any], list]:
        # 2xx uniquement sinon on lève avec contenu utile
        if r.status_code // 100 != 2:
            txt = r.text[:300] if isinstance(r.text, str) else str(r.text)
            raise BitgetError(f"HTTP {r.status_code}: {txt}")
        try:
            js = r.json()
        except Exception as e:
            raise BitgetError(f"Invalid JSON: {e}; body={r.text[:200]}")
        # Bitget renvoie parfois une LISTE (candles) au lieu d'un objet
        if isinstance(js, list):
            return js
        if isinstance(js, dict):
            code = str(js.get("code", "00000"))
            # certains endpoints publics n'ont pas de 'code'
            if "code" in js and code not in ("00000", "0", "200"):
                raise BitgetError(f"API code={code} msg={js.get('msg')} data={js.get('data')}")
            return js
        raise BitgetError(f"Unexpected payload type: {type(js)}")

    def _get(self, path: str, params: Dict[str, Any]) -> Union[Dict[str, Any], list]:
        url = f"{self.BASE}{path}"
        last: Optional[Exception] = None
        for _ in range(self.RETRIES + 1):
            try:
                r = self.session.get(url, params=params, timeout=self.TIMEOUT)
                return self._ok(r)
            except Exception as e:
                last = e
                time.sleep(0.3)
        raise BitgetError(str(last) if last else "GET failed without exception")
