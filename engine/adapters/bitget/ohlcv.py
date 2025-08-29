from __future__ import annotations
from typing import List, Optional, Dict, Any, Tuple
from .base import BitgetBase, BitgetError

class OhlcvClient(BitgetBase):
    """
    Client public OHLCV pour les futures linéaires (umcbl).
    - Ne passe PAS 'limit' à l'API (certaines routes le refusent) ; on coupe côté client.
    - Essaie plusieurs variantes de routes/params pour éviter 400172.
    """

    def _fetch_variants(self, symbol: str, tf: str) -> List[Tuple[str, Dict[str, Any]]]:
        sym = f"{symbol}_{self.market.upper()}"
        gran = self.tf_to_granularity(tf)      # '1m', '5m', '1h', etc.
        return [
            ("/api/mix/v1/market/candles",          {"symbol": sym, "granularity": gran}),
            ("/api/mix/v1/market/candles",          {"symbol": sym, "granularity": "60"}),   # alt num
            ("/api/mix/v1/market/history-candles",  {"symbol": sym, "granularity": gran}),
            ("/api/mix/v1/market/history-candles",  {"symbol": sym, "granularity": "60"}),
        ]

    def fetch_ohlcv(self, symbol: str, tf: str = "1m", limit: int = 200) -> List[list]:
        """
        Retourne une liste de lignes:
        [timestamp_ms, open, high, low, close, volume, quote_volume(None)]
        Trie du plus ancien -> plus récent, tronqué à `limit`.
        """
        last_err: Optional[Exception] = None
        data: List[list] = []

        for path, params in self._fetch_variants(symbol, tf):
            try:
                js = self._get(path, params=params, auth=False)
                payload = (js.get("data") if isinstance(js, dict) else js) or []
                if not isinstance(payload, list):
                    raise BitgetError(f"Réponse inattendue: {js}")
                # Bitget renvoie du plus récent -> plus ancien ; on inverse
                rows = list(reversed(payload))
                out: List[list] = []
                for row in rows:
                    # format API: [ts, open, high, low, close, volume, ...] (en str)
                    ts, o, h, l, c, v = row[:6]
                    out.append([
                        int(ts),
                        float(o), float(h), float(l), float(c),
                        float(v),
                        None,   # quote_volume inconnu ici
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

        # Tronque côté client
        if limit and limit > 0:
            data = data[-limit:]

        return data
