from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class BotConfig:
    MEXC_ACCESS_KEY: str
    MEXC_SECRET_KEY: str
    PAPER_TRADE: bool
    SYMBOL: str
    INTERVAL: str
    EMA_FAST: int
    EMA_SLOW: int
    RISK_PCT_EQUITY: float
    LEVERAGE: int
    OPEN_TYPE: int
    STOP_LOSS_PCT: float
    TAKE_PROFIT_PCT: float
    MAX_KLINES: int
    LOOP_SLEEP_SECS: int
    RECV_WINDOW: int
    LOG_DIR: str
    BASE_URL: str


def load_config() -> BotConfig:
    env = os.getenv
    return BotConfig(
        MEXC_ACCESS_KEY=env("MEXC_ACCESS_KEY", "A_METTRE"),
        MEXC_SECRET_KEY=env("MEXC_SECRET_KEY", "B_METTRE"),
        PAPER_TRADE=env("PAPER_TRADE", "true").lower() in ("1", "true", "yes", "y"),
        SYMBOL=env("SYMBOL", "BTC_USDT"),
        INTERVAL=env("INTERVAL", "Min1"),
        EMA_FAST=int(env("EMA_FAST", "9")),
        EMA_SLOW=int(env("EMA_SLOW", "21")),
        RISK_PCT_EQUITY=float(env("RISK_PCT_EQUITY", "0.01")),
        LEVERAGE=int(env("LEVERAGE", "5")),
        OPEN_TYPE=int(env("OPEN_TYPE", "1")),
        STOP_LOSS_PCT=float(env("STOP_LOSS_PCT", "0.006")),
        TAKE_PROFIT_PCT=float(env("TAKE_PROFIT_PCT", "0.012")),
        MAX_KLINES=int(env("MAX_KLINES", "400")),
        LOOP_SLEEP_SECS=int(env("LOOP_SLEEP_SECS", "10")),
        RECV_WINDOW=int(env("RECV_WINDOW", "30")),
        LOG_DIR=env("LOG_DIR", "./logs"),
        BASE_URL=env("MEXC_CONTRACT_BASE_URL", "https://contract.mexc.com"),
    )
