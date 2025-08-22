"""Configuration loading with optional Pydantic validation.

This module tries to use :mod:`pydantic` for robust validation of
environment variables, but gracefully falls back to a simple ``dataclass``
based approach when Pydantic is not available.  The public API mirrors the
previous design – callers simply import :func:`load_or_exit` and receive an
``AppConfig`` instance or the process exits with an error message.
"""

from __future__ import annotations

import os
import sys

# ---------------------------------------------------------------------------
# Optional Pydantic import.  Some execution environments might not provide
# Pydantic (e.g. minimal interpreters or restricted sandboxes).  In that case
# we continue with a light‑weight ``dataclass`` implementation.
# ---------------------------------------------------------------------------
try:  # pragma: no cover - behaviour depends on environment
    from pydantic import BaseModel, Field, ValidationError  # type: ignore

    _HAVE_PYDANTIC = True
except Exception:  # ImportError / environment restrictions
    _HAVE_PYDANTIC = False


if _HAVE_PYDANTIC:
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


    def load_or_exit() -> "AppConfig":
        """Load configuration from ``os.environ`` and validate.

        Exits the program with status code ``2`` when validation fails.
        """

        try:
            return AppConfig(
                BITGET_API_KEY=os.environ.get("BITGET_API_KEY"),
                BITGET_API_SECRET=os.environ.get("BITGET_API_SECRET"),
                BITGET_PASSPHRASE=os.environ.get("BITGET_PASSPHRASE"),
                RISK_PCT=float(os.environ.get("RISK_PCT", "0.01")),
                MIN_TRADE_USDT=float(os.environ.get("MIN_TRADE_USDT", "5")),
                LEVERAGE=float(os.environ.get("LEVERAGE", "1")),
                PAPER_TRADE=os.environ.get("PAPER_TRADE", "true").lower()
                in ("1", "true", "yes"),
                TELEGRAM_BOT_TOKEN=os.environ.get("TELEGRAM_BOT_TOKEN"),
                TELEGRAM_CHAT_ID=os.environ.get("TELEGRAM_CHAT_ID"),
            )
        except ValidationError as e:  # pragma: no cover - simple pass through
            print("[CONFIG] Invalid configuration:", e, file=sys.stderr)
            sys.exit(2)


else:  # -- Simple dataclass fallback ---------------------------------------
    from dataclasses import dataclass

    @dataclass
    class AppConfig:
        BITGET_API_KEY: str
        BITGET_API_SECRET: str
        BITGET_PASSPHRASE: str
        RISK_PCT: float = 0.01
        MIN_TRADE_USDT: float = 5.0
        LEVERAGE: float = 1.0
        PAPER_TRADE: bool = True
        TELEGRAM_BOT_TOKEN: str | None = None
        TELEGRAM_CHAT_ID: str | None = None


    def _env_bool(name: str, default: bool) -> bool:
        raw = os.environ.get(name)
        if raw is None:
            return default
        return raw.lower() in ("1", "true", "yes", "on")


    def load_or_exit() -> "AppConfig":
        """Minimal configuration loader used when Pydantic is unavailable."""

        key = os.environ.get("BITGET_API_KEY")
        sec = os.environ.get("BITGET_API_SECRET")
        pas = os.environ.get("BITGET_PASSPHRASE")
        if not key or not sec or not pas:
            print("[CONFIG] Missing BITGET_* credentials in env", file=sys.stderr)
            sys.exit(2)

        try:
            return AppConfig(
                BITGET_API_KEY=key,
                BITGET_API_SECRET=sec,
                BITGET_PASSPHRASE=pas,
                RISK_PCT=float(os.environ.get("RISK_PCT", "0.01")),
                MIN_TRADE_USDT=float(os.environ.get("MIN_TRADE_USDT", "5")),
                LEVERAGE=float(os.environ.get("LEVERAGE", "1")),
                PAPER_TRADE=_env_bool("PAPER_TRADE", True),
                TELEGRAM_BOT_TOKEN=os.environ.get("TELEGRAM_BOT_TOKEN"),
                TELEGRAM_CHAT_ID=os.environ.get("TELEGRAM_CHAT_ID"),
            )
        except Exception as e:  # pragma: no cover - defensive programming
            print(f"[CONFIG] Invalid configuration values: {e!r}", file=sys.stderr)
            sys.exit(2)

