from __future__ import annotations
from pydantic import BaseModel, Field, ValidationError
import os, sys


class AppConfig(BaseModel):
    BITGET_API_KEY: str = Field(..., min_length=10)
    BITGET_API_SECRET: str = Field(..., min_length=10)
    BITGET_PASSPHRASE: str = Field(..., min_length=3)
    RISK_PCT: float = Field(0.01, ge=0.0, le=0.05)
    MIN_TRADE_USDT: float = Field(5.0, ge=0.0)
    LEVERAGE: float = Field(1.0, ge=1.0, le=125.0)
    PAPER_TRADE: bool = Field(True)
    TELEGRAM_BOT_TOKEN: str | None = None
    TELEGRAM_CHAT_ID: str | None = None


def load_or_exit() -> AppConfig:
    try:
        return AppConfig(
            BITGET_API_KEY=os.environ.get("BITGET_API_KEY"),
            BITGET_API_SECRET=os.environ.get("BITGET_API_SECRET"),
            BITGET_PASSPHRASE=os.environ.get("BITGET_PASSPHRASE"),
            RISK_PCT=float(os.environ.get("RISK_PCT", "0.01")),
            MIN_TRADE_USDT=float(os.environ.get("MIN_TRADE_USDT", "5")),
            LEVERAGE=float(os.environ.get("LEVERAGE", "1")),
            PAPER_TRADE=os.environ.get("PAPER_TRADE", "true").lower() in ("1","true","yes"),
            TELEGRAM_BOT_TOKEN=os.environ.get("TELEGRAM_BOT_TOKEN"),
            TELEGRAM_CHAT_ID=os.environ.get("TELEGRAM_CHAT_ID"),
        )
    except ValidationError as e:
        print("[CONFIG] Invalid configuration:", e, file=sys.stderr)
        sys.exit(2)
