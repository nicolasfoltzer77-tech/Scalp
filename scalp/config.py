from __future__ import annotations

import os
from dataclasses import dataclass


def _get_bool(env_value: str, default: bool = False) -> bool:
    if env_value is None:
        return default
    return env_value.lower() in {"1", "true", "yes", "y"}


def _env(name: str, default: str | None = None) -> str | None:
    return os.getenv(name, default)


@dataclass
class BotConfig:
    mexc_access_key: str
    mexc_secret_key: str
    paper_trade: bool
    symbol: str
    interval: str
    ema_fast: int
    ema_slow: int
    risk_pct_equity: float
    leverage: int
    open_type: int
    stop_loss_pct: float
    take_profit_pct: float
    max_klines: int
    loop_sleep_secs: int
    recv_window: int
    log_dir: str
    base_url: str


def load_config() -> BotConfig:
    """Read environment variables and return validated BotConfig."""
    cfg = BotConfig(
        mexc_access_key=_env("MEXC_ACCESS_KEY", "A_METTRE"),
        mexc_secret_key=_env("MEXC_SECRET_KEY", "B_METTRE"),
        paper_trade=_get_bool(_env("PAPER_TRADE", "true"), True),
        symbol=_env("SYMBOL", "BTC_USDT"),
        interval=_env("INTERVAL", "Min1"),
        ema_fast=int(_env("EMA_FAST", "9")),
        ema_slow=int(_env("EMA_SLOW", "21")),
        risk_pct_equity=float(_env("RISK_PCT_EQUITY", "0.01")),
        leverage=int(_env("LEVERAGE", "5")),
        open_type=int(_env("OPEN_TYPE", "1")),
        stop_loss_pct=float(_env("STOP_LOSS_PCT", "0.006")),
        take_profit_pct=float(_env("TAKE_PROFIT_PCT", "0.012")),
        max_klines=int(_env("MAX_KLINES", "400")),
        loop_sleep_secs=int(_env("LOOP_SLEEP_SECS", "10")),
        recv_window=int(_env("RECV_WINDOW", "30")),
        log_dir=_env("LOG_DIR", "./logs"),
        base_url=_env("MEXC_CONTRACT_BASE_URL", "https://contract.mexc.com"),
    )

    # Basic validation
    if cfg.ema_fast <= 0 or cfg.ema_slow <= 0:
        raise ValueError("EMA periods must be positive")
    if cfg.risk_pct_equity <= 0 or cfg.leverage <= 0:
        raise ValueError("Risk percentage and leverage must be positive")
    if cfg.recv_window <= 0 or cfg.recv_window > 60:
        raise ValueError("recv_window must be in 1..60")
    if not cfg.symbol:
        raise ValueError("symbol must not be empty")

    return cfg
