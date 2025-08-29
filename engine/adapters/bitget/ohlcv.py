from __future__ import annotations
from typing import List, Optional, Dict, Any, Tuple
from .base import BitgetBase, BitgetError

class OhlcvClient(BitgetBase):
    """
    Client public OHLCV pour les futures (umcbl).
    Bitget exige 'granularity' en secondes (int).
    """

    TF_TO_SEC = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "1h": 3600,
        "4h": 14400,
        "1d": 86400,
    }

    def _fetch_variants(self, symbol: str, tf: str) -> List[Tuple[str, Dict[str, Any]]]:
        sym = f"{symbol}_{self.market.upper()}"
        sec = self.TF_TO_SEC.get(tf)
        if not sec:
            raise BitgetError(f"Unsupported timeframe {tf}")
        return [
            ("/api/mix/v1/market/candles",         {"symbol": sym, "granularity": sec}),
            ("/api/mix/v1/market/history-candles", {"symbol": sym, "granularity": sec}),
        ]

    def fetch_ohlcv(self, symbol: str, tf: str = "1m", limit: int = 200) -> List[list]:
        """
        Retourne [timestamp_ms, open, high, low, close, volume, None]
        Trie ancien -> récent, tronqué à limit.
        """
        last_err: Optional[Exception] = None
        data: List[list] = []

        for path, params in self._fetch_variants(symbol, tf):
            try:
                js = self._get(path, params=params, auth=False)
                payload = (js.get("data") if isinstance(js, dict) else js) or []
                if not isinstance(payload, list):
                    raise BitgetError(f"Réponse inattendue: {js}")
                rows = list(reversed(payload))
                out: List[list] = []
                for row in rows:
                    ts, o, h, l, c, v = row[:6]
                    out.append([
                        int(ts),
                        float(o), float(h), float(l), float(c),
                        float(v),
                        None,
                    ])
                data = out
                break
            except Exception as e:
                last_err = e
                continue

        if not data:
            raise BitgetError(
                f"Aucune variante valide pour {symbol} {tf} "
                f"(dernier échec: {last_err})"
            )

        return data[-limit:] if limit else data
