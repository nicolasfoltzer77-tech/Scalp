# scalper/exchanges/bitget.py
from __future__ import annotations
import time
import requests
from typing import List

class BitgetExchange:
    """
    Client léger Bitget pour récupérer des OHLCV SPOT en public (pas d'auth).
    Retourne des lignes au format: [ts_ms, open, high, low, close, volume]
    """

    BASE = "https://api.bitget.com"
    # Mapping timeframe -> paramètre 'period' (spot)
    TF = {
        "1m": "1min",
        "3m": "3min",
        "5m": "5min",
        "15m": "15min",
        "30m": "30min",
        "1h": "1hour",
        "4h": "4hour",
        "1d": "1day",
    }

    def __init__(self, api_key: str = "", api_secret: str = "", api_passphrase: str = "", timeout: int = 15):
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def _get(self, path: str, params: dict) -> dict:
        url = f"{self.BASE}{path}"
        r = self.session.get(url, params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def get_ohlcv(self, *, symbol: str, timeframe: str, limit: int = 1000) -> List[List[float]]:
        """
        Candles SPOT (ordre chronologique ascendant).
        Docs: GET /api/spot/v1/market/candles
        Params attendus:
          symbol: ex 'BTCUSDT'
          period: ex '5min'
          limit : <= 1000 (Bitget)
        Réponse Bitget: liste de listes [ts, open, high, low, close, volume, turnover]
        NB: renvoyée par Bitget en ordre *décroissant* -> on renverse.
        """
        tf = timeframe.lower()
        period = self.TF.get(tf)
        if not period:
            raise ValueError(f"Timeframe non supporté: {timeframe} (supportés: {list(self.TF)})")

        params = {"symbol": symbol.upper(), "period": period, "limit": min(int(limit), 1000)}
        data = self._get("/api/spot/v1/market/candles", params=params)

        # Tolérance de structure (certaines versions renvoient {"code":...,"data":[...]} )
        rows = data.get("data", data)
        if not isinstance(rows, list):
            raise ValueError(f"Réponse inattendue Bitget: {data}")

        out: List[List[float]] = []
        # Bitget renvoie généralement: [timestamp, open, high, low, close, volume, turnover]
        for r in rows:
            # robustesse: accepter str ou nombres, tailles variables
            ts = float(r[0])
            op = float(r[1]); hi = float(r[2]); lo = float(r[3]); cl = float(r[4]); vol = float(r[5])
            out.append([ts, op, hi, lo, cl, vol])

        # ordre chrono ASC (le bot/backtest attend croissant)
        out.sort(key=lambda x: x[0])
        return out