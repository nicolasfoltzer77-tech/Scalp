from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple, Union
from .base import BitgetBase, BitgetError

class OhlcvClient(BitgetBase):
    """
    OHLCV public pour futures (umcbl) ou spot (spbl).
    - timeframe mappé en secondes (string).
    - symbol final: BTCUSDT_UMCBL / BTCUSDT_SPBL (selon self.market).
    """

    TF_TO_SEC = {
        "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
        "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600, "8h": 28800, "12h": 43200,
        "1d": 86400, "3d": 259200, "1w": 604800
    }

    def _routes(self, symbol: str, tf: str, limit: int) -> List[Tuple[str, Dict[str, Any]]]:
        sec = self.TF_TO_SEC.get(tf)
        if not sec:
            raise BitgetError(f"Unsupported timeframe: {tf}")
        sym = f"{symbol}_{self.market.upper()}"
        params = {"symbol": sym, "granularity": str(sec)}  # granularity en STRING
        if limit:
            params["limit"] = int(limit)
        # ordre: candles (live) puis history-candles (rétro)
        return [
            ("/api/mix/v1/market/candles", params),
            ("/api/mix/v1/market/history-candles", params),
        ] if self.market.endswith("cbl") else [
            ("/api/spot/v1/market/candles", params),  # fallback spot
        ]

    def fetch_ohlcv(self, symbol: str, tf: str = "1m", limit: int = 200) -> List[List[Union[int, float, None]]]:
        last_err: Optional[Exception] = None
        for path, params in self._routes(symbol, tf, limit):
            try:
                js = self._get(path, params)
                payload = (js.get("data") if isinstance(js, dict) else js) or []
                if not isinstance(payload, list):
                    raise BitgetError(f"Unexpected payload: {type(payload)}")
                # Bitget renvoie récent -> ancien : on inverse
                rows = list(reversed(payload))
                out: List[List[Union[int, float, None]]] = []
                for row in rows:
                    # format attendu: [ts, open, high, low, close, volume, ...]
                    ts, o, h, l, c, v = row[:6]
                    out.append([int(ts), float(o), float(h), float(l), float(c), float(v), None])
                return out[-limit:] if limit else out
            except Exception as e:
                last_err = e
                continue
        raise BitgetError(
            f"Aucune variante valide pour {symbol} {tf} "
            f"(dernier échec: {last_err})"
        )
