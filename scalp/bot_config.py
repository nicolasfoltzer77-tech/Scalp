import os


DEFAULT_SYMBOL = os.getenv("SYMBOL") or "BTCUSDT"

CONFIG = {
    "BITGET_ACCESS_KEY": os.getenv("BITGET_API_KEY")
    or os.getenv("BITGET_ACCESS_KEY", "A_METTRE"),
    "BITGET_SECRET_KEY": os.getenv("BITGET_API_SECRET")
    or os.getenv("BITGET_SECRET_KEY", "B_METTRE"),
    "BITGET_PASSPHRASE": os.getenv("BITGET_API_PASSPHRASE", ""),
    "PAPER_TRADE": os.getenv("PAPER_TRADE", "true").lower() in ("1", "true", "yes", "y"),
    "SYMBOL": DEFAULT_SYMBOL,
    "PRODUCT_TYPE": os.getenv("BITGET_PRODUCT_TYPE", "USDT-FUTURES"),
    "MARGIN_COIN": os.getenv("BITGET_MARGIN_COIN", "USDT"),
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
    "BASE_URL": os.getenv("BITGET_CONTRACT_BASE_URL", "https://api.bitget.com"),
    "FEE_RATE": float(os.getenv("FEE_RATE", "0.0")),
    "MAX_DAILY_LOSS_PCT": float(os.getenv("MAX_DAILY_LOSS_PCT", "5.0")),
    "MAX_DAILY_PROFIT_PCT": float(os.getenv("MAX_DAILY_PROFIT_PCT", "5.0")),
    "MAX_POSITIONS": int(os.getenv("MAX_POSITIONS", "1")),
}

