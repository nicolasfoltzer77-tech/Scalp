# bot.py
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from typing import Any

from scalper.exchange.bitget_ccxt import BitgetExchange
from scalper.live.notify import build_notifier_and_commands
from scalper.live.orchestrator import run_orchestrator


# ---------- Déps minimales ----------
def ensure_deps() -> None:
    def _pip(pkg: str) -> None:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", pkg])
    try:
        import ccxt  # noqa: F401
    except ImportError:
        print("[deps] install ccxt…"); _pip("ccxt")
    try:
        import aiohttp  # noqa: F401
    except ImportError:
        print("[deps] install aiohttp…"); _pip("aiohttp")


# ---------- .env simple (sans dépendance) ----------
def load_dotenv_simple(path: str) -> None:
    if not os.path.isfile(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, v = s.split("=", 1)
                k = k.strip(); v = v.strip()
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass


# ---------- Config runtime ----------
def load_run_config() -> dict[str, Any]:
    # charge /notebooks/.env si présent (pour ton cas d'env global notebooks)
    load_dotenv_simple("/notebooks/.env")

    symbols = os.environ.get(
        "TOP_SYMBOLS",
        "BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,DOGEUSDT,ADAUSDT,LTCUSDT,AVAXUSDT,LINKUSDT",
    ).split(",")

    cfg = {
        "TIMEFRAME": os.environ.get("TIMEFRAME", "5m"),
        "TOP_SYMBOLS": [s.strip() for s in symbols if s.strip()],
        "FETCH_LIMIT": int(os.environ.get("FETCH_LIMIT", "1000")),
        "DATA_DIR": os.environ.get("DATA_DIR", "/notebooks/data"),
        "USE_CACHE": os.environ.get("USE_CACHE", "1") == "1",
        "CACHE_MIN_FRESH_SECONDS": int(os.environ.get("CACHE_MIN_FRESH_SECONDS", "0")),
        # Telegram
        "TELEGRAM_TOKEN": os.environ.get("TELEGRAM_TOKEN"),
        "TELEGRAM_CHAT_ID": os.environ.get("TELEGRAM_CHAT_ID"),
        # Bitget API (facultatif pour OHLCV public)
        "BITGET_API_KEY": os.environ.get("BITGET_API_KEY"),
        "BITGET_API_SECRET": os.environ.get("BITGET_API_SECRET"),
        "BITGET_API_PASSPHRASE": os.environ.get("BITGET_API_PASSPHRASE"),
    }

    print(
        "[notify] TELEGRAM configured."
        if (cfg["TELEGRAM_TOKEN"] and cfg["TELEGRAM_CHAT_ID"])
        else "[notify] TELEGRAM not configured -> Null notifier will be used."
    )
    return cfg


async def warmup_cache(exchange: BitgetExchange, symbols: list[str], tf: str, limit: int) -> None:
    for s in symbols:
        try:
            await exchange.fetch_ohlcv(s, tf, limit)
            print(f"[cache] warmup OK for {s}")
        except Exception as e:  # noqa: BLE001
            print(f"[cache] warmup FAIL for {s}: {e}")


async def main() -> None:
    ensure_deps()
    cfg = load_run_config()

    ex = BitgetExchange(
        api_key=cfg["BITGET_API_KEY"],
        secret=cfg["BITGET_API_SECRET"],
        password=cfg["BITGET_API_PASSPHRASE"],
        data_dir=cfg["DATA_DIR"],
        use_cache=cfg["USE_CACHE"],
        min_fresh_seconds=cfg["CACHE_MIN_FRESH_SECONDS"],
        spot=True,
    )

    await warmup_cache(ex, cfg["TOP_SYMBOLS"], cfg["TIMEFRAME"], cfg["FETCH_LIMIT"])

    notifier, command_stream_factory = await build_notifier_and_commands(cfg)

    try:
        await run_orchestrator(
            exchange=ex,
            config=cfg,
            notifier=notifier,
            command_stream_factory=command_stream_factory,
        )
    finally:
        await notifier.close()
        await ex.close()


if __name__ == "__main__":
    asyncio.run(main())