import logging
import os
from typing import List, Tuple

import requests


def fetch_pairs_with_fees_from_mexc(
    base_url: str | None = None,
) -> List[Tuple[str, float, float]]:
    """Retrieve trading pairs and their maker/taker fee rates from MEXC."""

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
        logging.debug("%s: maker=%s, taker=%s", sym, maker, taker)
        results.append((sym, maker, taker))
    return results


DEFAULT_SYMBOL = os.getenv("SYMBOL") or "BTC_USDT"

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
}

