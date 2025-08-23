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


# -------- Dépendances minimales (ccxt + aiohttp) ----------
def ensure_deps() -> None:
    def _pip(pkg: str) -> None:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", pkg])

    try:
        import ccxt  # noqa: F401
    except ImportError:
        print("[deps] install ccxt…")
        _pip("ccxt")

    try:
        import aiohttp  # noqa: F401
    except ImportError:
        print("[deps] install aiohttp…")
        _pip("aiohttp")


# -------- Config runtime ----------
def load_run_config() -> dict[str, Any]:
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
        # Telegram (facultatif)
        "TELEGRAM_TOKEN": os.environ.get("TELEGRAM_TOKEN"),
        "TELEGRAM_CHAT_ID": os.environ.get("TELEGRAM_CHAT_ID"),
        # Bitget creds (facultatif pour OHLCV public)
        "BITGET_API_KEY": os.environ.get("BITGET_API_KEY"),
        "BITGET_API_SECRET": os.environ.get("BITGET_API_SECRET"),
        "BITGET_API_PASSPHRASE": os.environ.get("BITGET_API_PASSPHRASE"),
    }

    # Log clair du mode notifier
    if cfg["TELEGRAM_TOKEN"] and cfg["TELEGRAM_CHAT_ID"]:
        print("[notify] TELEGRAM configured.")
    else:
        print("[notify] TELEGRAM not configured -> Null notifier will be used.")

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

    # Échange Bitget (spot + cache CSV)
    ex = BitgetExchange(
        api_key=cfg["BITGET_API_KEY"],
        secret=cfg["BITGET_API_SECRET"],
        password=cfg["BITGET_API_PASSPHRASE"],
        data_dir=cfg["DATA_DIR"],
        use_cache=cfg["USE_CACHE"],
        min_fresh_seconds=cfg["CACHE_MIN_FRESH_SECONDS"],
        spot=True,
    )

    # Pré-chauffe cache pour démarrer vite
    await warmup_cache(ex, cfg["TOP_SYMBOLS"], cfg["TIMEFRAME"], cfg["FETCH_LIMIT"])

    # Notifier + commands
    notifier, command_stream_factory = await build_notifier_and_commands(cfg)

    # Démarre orchestrateur (il sait gérer notifier/commands passés en argument)
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