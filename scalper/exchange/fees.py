# scalper/exchange/fees.py
from __future__ import annotations

from typing import Dict, Iterable

# Valeurs par défaut (Bitget spot/futures ~ ordre de grandeur ; sera écrasé quand on charge les frais)
DEFAULT_TAKER_BPS = 6    # 0.06%
DEFAULT_MAKER_BPS = 2    # 0.02%

# Cache local: symbol -> {"taker_bps": int, "maker_bps": int}
_FEES_BY_SYMBOL: Dict[str, Dict[str, float]] = {}


def get_fee(symbol: str, kind: str = "taker") -> float:
    """
    Retourne le fee rate (fraction, ex 0.0006) pour 'symbol' et 'kind' ("taker" ou "maker").
    Utilise le cache alimenté par load_bitget_fees(), sinon valeurs par défaut.
    """
    rec = _FEES_BY_SYMBOL.get(symbol, {"taker_bps": DEFAULT_TAKER_BPS, "maker_bps": DEFAULT_MAKER_BPS})
    bps = rec["taker_bps"] if kind == "taker" else rec["maker_bps"]
    return float(bps) / 10_000.0


async def load_bitget_fees(exchange, symbols: Iterable[str]) -> Dict[str, Dict[str, float]]:
    """
    Tente de charger les frais auprès de l'exchange (type ccxt):
      - fetch_trading_fees(symbols) si dispo
      - sinon fetch_trading_fee(symbol) pour chaque symbole
    Remplit le cache _FEES_BY_SYMBOL avec des BPS (entiers).
    """
    symbols = list(symbols)
    fees: Dict[str, Dict[str, float]] = {}

    try:
        if hasattr(exchange, "fetch_trading_fees"):
            data = await exchange.fetch_trading_fees(symbols)
            for s in symbols:
                d = (data or {}).get(s, {}) or {}
                taker = float(d.get("taker", DEFAULT_TAKER_BPS / 10_000))
                maker = float(d.get("maker", DEFAULT_MAKER_BPS / 10_000))
                fees[s] = {"taker_bps": round(taker * 10_000), "maker_bps": round(maker * 10_000)}
        else:
            for s in symbols:
                try:
                    d = await exchange.fetch_trading_fee(s)
                except Exception:
                    d = {}
                taker = float(d.get("taker", DEFAULT_TAKER_BPS / 10_000))
                maker = float(d.get("maker", DEFAULT_MAKER_BPS / 10_000))
                fees[s] = {"taker_bps": round(taker * 10_000), "maker_bps": round(maker * 10_000)}
    except Exception:
        # fallback: défauts
        for s in symbols:
            fees[s] = {"taker_bps": DEFAULT_TAKER_BPS, "maker_bps": DEFAULT_MAKER_BPS}

    # maj du cache
    _FEES_BY_SYMBOL.update(fees)
    return fees