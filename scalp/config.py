import os
from typing import Any, Dict


def load_config() -> Dict[str, Any]:
    return {
        "MEXC_ACCESS_KEY": os.getenv("MEXC_ACCESS_KEY", "A_METTRE"),
        "MEXC_SECRET_KEY": os.getenv("MEXC_SECRET_KEY", "B_METTRE"),
        "PAPER_TRADE": os.getenv("PAPER_TRADE", "true").lower() in ("1", "true", "yes", "y"),
        "SYMBOL": os.getenv("SYMBOL", "BTC_USDT"),
        "INTERVAL": os.getenv("INTERVAL", "Min1"),
        "EMA_FAST": int(os.getenv("EMA_FAST", "9")),
        "EMA_SLOW": int(os.getenv("EMA_SLOW", "21")),
        "RISK_PCT_EQUITY": float(os.getenv("RISK_PCT_EQUITY", "0.01")),
        "LEVERAGE": int(os.getenv("LEVERAGE", "5")),
        "OPEN_TYPE": int(os.getenv("OPEN_TYPE", "1")),
        "STOP_LOSS_PCT": float(os.getenv("STOP_LOSS_PCT", "0.006")),
        "TAKE_PROFIT_PCT": float(os.getenv("TAKE_PROFIT_PCT", "0.012")),
        "MAX_KLINES": int(os.getenv("MAX_KLINES", "400")),
        "LOOP_SLEEP_SECS": int(os.getenv("LOOP_SLEEP_SECS", "10")),
        "RECV_WINDOW": int(os.getenv("RECV_WINDOW", "30")),
        "LOG_DIR": os.getenv("LOG_DIR", "./logs"),
        "BASE_URL": os.getenv("MEXC_CONTRACT_BASE_URL", "https://contract.mexc.com"),
    }
