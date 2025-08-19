import os
from typing import List, Tuple

import requests


def _base(sym: str) -> str:
    """Return base asset for a symbol like ``BTC_USDT`` or ``BTCUSDT``."""
    if "_" in sym:
        return sym.split("_", 1)[0]
    if sym.endswith("USDT"):
        return sym[:-4]
    if sym.endswith("USD"):
        return sym[:-3]
    return sym


def _dedup_by_base(symbols: List[str]) -> List[str]:
    """Remove duplicate symbols that share the same base asset."""
    seen = set()
    unique: List[str] = []
    for sym in symbols:
        b = _base(sym)
        if b in seen:
            continue
        seen.add(b)
        unique.append(sym)
    return unique


def fetch_pairs_with_fees_from_mexc(
    base_url: str | None = None,
) -> List[Tuple[str, float, float]]:
    """Retrieve trading pairs and their maker/taker fee rates from MEXC.

    The function prints each pair as it is parsed so that callers can observe
    the data returned by the exchange step by step.
    """

    base = base_url or os.getenv("MEXC_CONTRACT_BASE_URL", "https://contract.mexc.com")
    url = f"{base}/api/v1/contract/fee-rate"
    try:
        resp = requests.get(url, timeout=5)
        data = resp.json()
    except Exception:
        return []

    results: List[Tuple[str, float, float]] = []
    for row in data.get("data", []):
        sym = row.get("symbol")
        try:
            taker = float(row.get("takerFeeRate", 1))
            maker = float(row.get("makerFeeRate", 1))
        except (TypeError, ValueError):
            continue
        if not sym:
            continue
        print(f"{sym}: maker={maker}, taker={taker}")
        results.append((sym, maker, taker))
    return results


def fetch_pairs_from_mexc(base_url: str | None = None) -> List[str]:
    """Query MEXC for available contract symbols.

    The endpoint ``/api/v1/contract/fee-rate`` returns the maker and taker fee
    for each contract symbol. We expose all symbols returned by the API but
    collapse variants that share the same base asset (e.g. ``BTC_USDT`` and
    ``BTC_USDC``) so that the list contains at most one entry per crypto.
    """

    pairs_with_fees = fetch_pairs_with_fees_from_mexc(base_url)

    pairs = [sym for sym, _maker, _taker in pairs_with_fees]
    unique = _dedup_by_base(pairs)
    print(f"Pairs: {unique}")
    return unique


def load_pairs() -> List[str]:
    """Load trading pairs from env or from MEXC."""

    env = os.getenv("PAIRS")
    if env:
        pairs = [p.strip() for p in env.split(",") if p.strip()]
        return _dedup_by_base(pairs)
    return fetch_pairs_from_mexc()


PAIRS = load_pairs()
DEFAULT_SYMBOL = os.getenv("SYMBOL") or (PAIRS[0] if PAIRS else "BTC_USDT")

CONFIG = {
    "MEXC_ACCESS_KEY": os.getenv("MEXC_ACCESS_KEY", "A_METTRE"),
    "MEXC_SECRET_KEY": os.getenv("MEXC_SECRET_KEY", "B_METTRE"),
    "PAPER_TRADE": os.getenv("PAPER_TRADE", "true").lower() in ("1", "true", "yes", "y"),
    "SYMBOL": DEFAULT_SYMBOL,
    "INTERVAL": os.getenv("INTERVAL", "Min1"),
    "EMA_FAST": int(os.getenv("EMA_FAST", "9")),
    "EMA_SLOW": int(os.getenv("EMA_SLOW", "21")),
    "MACD_FAST": int(os.getenv("MACD_FAST", "12")),
    "MACD_SLOW": int(os.getenv("MACD_SLOW", "26")),
    "MACD_SIGNAL": int(os.getenv("MACD_SIGNAL", "9")),
    "EMA_TREND_PERIOD": int(os.getenv("EMA_TREND_PERIOD", "200")),
    "RISK_PCT_EQUITY": float(os.getenv("RISK_PCT_EQUITY", "0.01")),
    "LEVERAGE": int(os.getenv("LEVERAGE", "5")),
    "RISK_LEVEL": int(os.getenv("RISK_LEVEL", "2")),
    "OPEN_TYPE": int(os.getenv("OPEN_TYPE", "1")),
    "STOP_LOSS_PCT": float(os.getenv("STOP_LOSS_PCT", "0.006")),
    "TAKE_PROFIT_PCT": float(os.getenv("TAKE_PROFIT_PCT", "0.012")),
    "ATR_PERIOD": int(os.getenv("ATR_PERIOD", "14")),
    "TRAIL_ATR_MULT": float(os.getenv("TRAIL_ATR_MULT", "0.75")),
    "SCALE_IN_ATR_MULT": float(os.getenv("SCALE_IN_ATR_MULT", "0.5")),
    "PROGRESS_MIN": float(os.getenv("PROGRESS_MIN", "15")),
    "TIMEOUT_MIN": float(os.getenv("TIMEOUT_MIN", "30")),
    "MAX_KLINES": int(os.getenv("MAX_KLINES", "400")),
    "LOOP_SLEEP_SECS": int(os.getenv("LOOP_SLEEP_SECS", "10")),
    "RECV_WINDOW": int(os.getenv("RECV_WINDOW", "30")),
    "LOG_DIR": os.getenv("LOG_DIR", "./logs"),
    "BASE_URL": os.getenv("MEXC_CONTRACT_BASE_URL", "https://contract.mexc.com"),
    "FEE_RATE": float(os.getenv("FEE_RATE", "0.0")),
    "MAX_DAILY_LOSS_PCT": float(os.getenv("MAX_DAILY_LOSS_PCT", "5.0")),
    "MAX_DAILY_PROFIT_PCT": float(os.getenv("MAX_DAILY_PROFIT_PCT", "5.0")),
    "MAX_POSITIONS": int(os.getenv("MAX_POSITIONS", "1")),
    "PAIRS": PAIRS,
}

