from __future__ import annotations
from typing import List, Optional
from .base import BitgetBase, BitgetError

class OhlcvClient(BitgetBase):
    """
    Client public OHLCV pour les futures linéaires (umcbl).
    """

    def fetch_ohlcv(self, symbol: str, tf: str = "1m", limit: int = 200) -> List[list]:
        """
        Retourne une liste de lignes:
        [timestamp_ms, open, high, low, close, volume, quote_volume(None)]
        """
        gran = self.tf_to_granularity(tf)
        path = "/api/mix/v1/market/candles"
        params = {
            "symbol": f"{symbol}_{self.market.upper()}",
            "granularity": gran,
            "limit": str(limit),
        }
        js = self._get(path, params=params, auth=False)

        # L’API renvoie data newest -> oldest, on inverse
        data = (js.get("data") if isinstance(js, dict) else js) or []
        data = list(reversed(data))

        out: List[list] = []
        for row in data:
            # format: [ts, open, high, low, close, volume] (tous en string)
            ts, o, h, l, c, v = row[:6]
            out.append([
                int(ts),
                float(o), float(h), float(l), float(c),
                float(v),
                None,
            ])
        return out
