# scalp/config.py
from __future__ import annotations
import os, sys
from typing import Optional

# ---------------------------
#  Chargement .env (sans dep)
# ---------------------------
def _load_dotenv_if_present(path: str = ".env") -> None:
    try:
        if not os.path.isfile(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, v = s.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                # ne pas écraser une var déjà définie par l'env
                os.environ.setdefault(k, v)
    except Exception:
        pass

_load_dotenv_if_present()

# ---------------------------
#  Aliases variables d'env
# ---------------------------
def _env_alias(name: str, *aliases: str) -> Optional[str]:
    """Retourne la première valeur non nulle parmi name et ses alias."""
    if name in os.environ and os.environ[name]:
        return os.environ[name]
    for a in aliases:
        v = os.environ.get(a)
        if v:
            return v
    return None

def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.lower() in ("1", "true", "yes", "on")

# ---------------------------
#  Pydantic v1 si dispo
# ---------------------------
try:
    from pydantic import BaseModel, Field, ValidationError  # type: ignore
    _HAVE_PYDANTIC = True
except Exception:
    _HAVE_PYDANTIC = False

if _HAVE_PYDANTIC:

    class AppConfig(BaseModel):
        # Clés Bitget
        BITGET_API_KEY: str = Field(..., min_length=3)
        BITGET_API_SECRET: str = Field(..., min_length=3)
        BITGET_PASSPHRASE: str = Field(..., min_length=1)

        # Trading
        RISK_PCT: float = Field(0.01, ge=0.0, le=0.2)
        MIN_TRADE_USDT: float = Field(5.0, ge=0.0)
        LEVERAGE: float = Field(1.0, ge=1.0, le=125.0)
        PAPER_TRADE: bool = Field(True)

        # Telegram (facultatif)
        TELEGRAM_BOT_TOKEN: Optional[str] = None
        TELEGRAM_CHAT_ID: Optional[str] = None

    def load_or_exit() -> "AppConfig":
        try:
            # supporte aussi ACCESS_KEY/SECRET_KEY (alias)
            api_key = _env_alias("BITGET_API_KEY", "BITGET_ACCESS_KEY")
            api_sec = _env_alias("BITGET_API_SECRET", "BITGET_SECRET_KEY")
            api_pass = _env_alias("BITGET_PASSPHRASE", "BITGET_PASSWORD", "API_PASSPHRASE")

            return AppConfig(
                BITGET_API_KEY=api_key,
                BITGET_API_SECRET=api_sec,
                BITGET_PASSPHRASE=api_pass,
                RISK_PCT=float(os.environ.get("RISK_PCT", "0.01")),
                MIN_TRADE_USDT=float(os.environ.get("MIN_TRADE_USDT", "5")),
                LEVERAGE=float(os.environ.get("LEVERAGE", "1")),
                PAPER_TRADE=_env_bool("PAPER_TRADE", True),
                TELEGRAM_BOT_TOKEN=_env_alias("TELEGRAM_BOT_TOKEN"),
                TELEGRAM_CHAT_ID=_env_alias("TELEGRAM_CHAT_ID"),
            )
        except ValidationError as e:
            print("[CONFIG] Invalid configuration:", e, file=sys.stderr)
            sys.exit(2)

else:
    # ---------------------------
    #  Fallback dataclass simple
    # ---------------------------
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

        TELEGRAM_BOT_TOKEN: Optional[str] = None
        TELEGRAM_CHAT_ID: Optional[str] = None

    def load_or_exit() -> "AppConfig":
        api_key = _env_alias("BITGET_API_KEY", "BITGET_ACCESS_KEY")
        api_sec = _env_alias("BITGET_API_SECRET", "BITGET_SECRET_KEY")
        api_pass = _env_alias("BITGET_PASSPHRASE", "BITGET_PASSWORD", "API_PASSPHRASE")

        if not api_key or not api_sec or not api_pass:
            print("[CONFIG] Missing Bitget credentials. Expected either:", file=sys.stderr)
            print("        - BITGET_API_KEY / BITGET_API_SECRET / BITGET_PASSPHRASE", file=sys.stderr)
            print("          or", file=sys.stderr)
            print("        - BITGET_ACCESS_KEY / BITGET_SECRET_KEY / BITGET_PASSPHRASE", file=sys.stderr)
            sys.exit(2)

        try:
            return AppConfig(
                BITGET_API_KEY=api_key,
                BITGET_API_SECRET=api_sec,
                BITGET_PASSPHRASE=api_pass,
                RISK_PCT=float(os.environ.get("RISK_PCT", "0.01")),
                MIN_TRADE_USDT=float(os.environ.get("MIN_TRADE_USDT", "5")),
                LEVERAGE=float(os.environ.get("LEVERAGE", "1")),
                PAPER_TRADE=_env_bool("PAPER_TRADE", True),
                TELEGRAM_BOT_TOKEN=_env_alias("TELEGRAM_BOT_TOKEN"),
                TELEGRAM_CHAT_ID=_env_alias("TELEGRAM_CHAT_ID"),
            )
        except Exception as e:
            print(f"[CONFIG] Invalid configuration values: {e!r}", file=sys.stderr)
            sys.exit(2)