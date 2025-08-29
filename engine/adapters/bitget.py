# -*- coding: utf-8 -*-
"""
Bitget client (Spot + Futures UMCBL).
Fix : suffix auto-intelligent (ne double pas).
"""

import requests

DEFAULT_BASE = "https://api.bitget.com"

_TF_MAP = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "1h": "1hour",
    "4h": "4hour",
    "1d": "1day",
}

class BitgetClient:
    def __init__(self, market="umcbl", base_url=None, timeout=15):
        self.market = market.lower()
        if self.market not in ("umcbl", "spbl"):
            raise ValueError("market must be 'umcbl' or 'spbl'")
        self.base_url = base_url or DEFAULT_BASE
        self.timeout = timeout
        self.sess = requests.Session()

    def _ok(self, r):
        if not r.ok:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text}")
        j = r.json()
        code = str(j.get("code", ""))
        if code not in ("0", "00000", ""):
            raise RuntimeError(f"API error {code}: {j}")
        return j.get("data", [])

    def _symbol(self, sym: str) -> str:
        sym = sym.upper().replace("-", "")
        suffix = "_UMCBL" if self.market == "umcbl" else "_SPBL"
        if not sym.endswith(suffix):
            return f"{sym}{suffix}"
        return sym

    def _granularity(self, tf: str) -> str:
        if tf not in _TF_MAP:
            raise ValueError(f"Unsupported tf {tf}")
        return _TF_MAP[tf]

    def fetch_ohlcv(self, symbol: str, timeframe="1m", limit=100):
        sym = self._symbol(symbol)
        gran = self._granularity(timeframe)

        if self.market == "umcbl":
            url = f"{self.base_url}/api/mix/v1/market/history-candles"
            params = {"symbol": sym, "granularity": gran, "limit": limit, "productType": "umcbl"}
        else:
            url = f"{self.base_url}/api/spot/v1/market/history-candles"
            params = {"symbol": sym, "granularity": gran, "limit": limit}

        r = self.sess.get(url, params=params, timeout=self.timeout)
        return self._ok(r)

