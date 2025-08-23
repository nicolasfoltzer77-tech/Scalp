# scalp/exchange/fees.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple

async def load_bitget_fees(exchange, symbols: List[str]) -> Dict[str, Dict[str, float]]:
    """
    Retourne un dict {symbol: {"maker_bps": float, "taker_bps": float}}
    en se basant sur les marchés de l'exchange (ex: CCXT bitget).
    - exchange.load_markets() doit remplir exchange.markets[symbol]["maker"/"taker"] (décimaux).
    - Si l'exchange expose fetch_trading_fee(s), on tente aussi.
    """
    # 1) charge les marchés (public fees — peut différer de tes fees utilisateur)
    try:
        if hasattr(exchange, "load_markets"):
            await exchange.load_markets()
    except Exception:
        pass

    fees: Dict[str, Dict[str, float]] = {}
    # 2) essaie par marché
    for sym in symbols:
        maker = None; taker = None
        m = None
        try:
            m = exchange.markets.get(sym) if hasattr(exchange, "markets") else None
        except Exception:
            m = None
        if m:
            maker = m.get("maker")
            taker = m.get("taker")

        # 3) fallback : fetch_trading_fee (si dispo)
        if (maker is None or taker is None) and hasattr(exchange, "fetch_trading_fee"):
            try:
                tf = await exchange.fetch_trading_fee(sym)
                maker = tf.get("maker", maker)
                taker = tf.get("taker", taker)
            except Exception:
                pass

        # 4) fallback global : fetch_trading_fees
        if (maker is None or taker is None) and hasattr(exchange, "fetch_trading_fees"):
            try:
                tfs = await exchange.fetch_trading_fees()
                tf = tfs.get(sym, {})
                maker = tf.get("maker", maker)
                taker = tf.get("taker", taker)
            except Exception:
                pass

        # 5) si rien trouvé, on garde 0 (évite de sur-estimer perf)
        maker_bps = float(maker * 10000.0) if isinstance(maker, (int, float)) else 0.0
        taker_bps = float(taker * 10000.0) if isinstance(taker, (int, float)) else 0.0
        fees[sym] = {"maker_bps": maker_bps, "taker_bps": taker_bps}
    return fees