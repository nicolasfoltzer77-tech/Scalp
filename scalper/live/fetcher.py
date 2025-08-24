# scalper/live/fetcher.py
from __future__ import annotations
from typing import Dict, List, Optional, Any

class DataFetcher:
    """
    Récupération OHLCV depuis un client d'exchange.
    Compatible:
      - Wrapper custom: client.get_ohlcv(symbol, timeframe, limit)
      - ccxt direct:    client.fetch_ohlcv(symbol, timeframe=..., limit=...)
    Retour standardisé: dict[str, list[float]] avec clés:
      timestamp, open, high, low, close, volume
    """
    def __init__(self, client: Any) -> None:
        self.client = client
        # Détection des méthodes disponibles
        self._has_get = hasattr(client, "get_ohlcv")
        self._has_fetch = hasattr(client, "fetch_ohlcv")

        if not (self._has_get or self._has_fetch):
            raise AttributeError(
                "Le client exchange doit exposer get_ohlcv(...) ou fetch_ohlcv(...). "
                "Ex: wrapper custom ou objet ccxt.bitget."
            )

    @staticmethod
    def _to_dict(rows: List[List[float]]) -> Dict[str, List[float]]:
        cols = ("timestamp", "open", "high", "low", "close", "volume")
        out = {k: [] for k in cols}
        for r in rows:
            # rows: [ts, open, high, low, close, volume]
            out["timestamp"].append(float(r[0]))
            out["open"].append(float(r[1]))
            out["high"].append(float(r[2]))
            out["low"].append(float(r[3]))
            out["close"].append(float(r[4]))
            out["volume"].append(float(r[5]))
        return out

    def fetch(self, symbol: str, timeframe: str, limit: int = 1500) -> Dict[str, List[float]]:
        if self._has_get:
            rows = self.client.get_ohlcv(symbol=symbol, timeframe=timeframe, limit=limit)
        else:
            # ccxt: fetch_ohlcv(symbol, timeframe=..., limit=...)
            rows = self.client.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        return self._to_dict(rows)

    def try_fetch_1h(self, symbol: str, limit: int = 1500) -> Optional[Dict[str, List[float]]]:
        try:
            if self._has_get:
                rows = self.client.get_ohlcv(symbol=symbol, timeframe="1h", limit=limit)
            else:
                rows = self.client.fetch_ohlcv(symbol, timeframe="1h", limit=limit)
            return self._to_dict(rows)
        except Exception:
            return None