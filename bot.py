# bot.py
from __future__ import annotations

import asyncio
import os
import sys
import subprocess
from typing import Any

from scalper.live.orchestrator import run_orchestrator
from scalper.exchange.bitget_ccxt import BitgetExchange


# -------------------------------------------------------------------
# S'assure que ccxt est dispo (premier run sur machine "neuve")
# -------------------------------------------------------------------
def ensure_ccxt() -> None:
    try:
        import ccxt  # noqa: F401
    except ImportError:
        print("[i] ccxt non installé, tentative d'installation...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "ccxt"])
        import ccxt  # noqa: F401


# -------------------------------------------------------------------
# Config runtime
# -------------------------------------------------------------------
def load_run_config() -> dict[str, Any]:
    symbols = os.environ.get(
        "TOP_SYMBOLS",
        "BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,DOGEUSDT,ADAUSDT,LTCUSDT,AVAXUSDT,LINKUSDT",
    ).split(",")

    return {
        "TIMEFRAME": os.environ.get("TIMEFRAME", "5m"),
        "TOP_SYMBOLS": [s.strip() for s in symbols if s.strip()],
        "TELEGRAM_TOKEN": os.environ.get("TELEGRAM_TOKEN"),
        "TELEGRAM_CHAT_ID": os.environ.get("TELEGRAM_CHAT_ID"),
        "FETCH_LIMIT": int(os.environ.get("FETCH_LIMIT", "1000")),
        # cache / données
        "DATA_DIR": os.environ.get("DATA_DIR", "/notebooks/data"),
        "USE_CACHE": os.environ.get("USE_CACHE", "1") == "1",
        "CACHE_MIN_FRESH_SECONDS": int(os.environ.get("CACHE_MIN_FRESH_SECONDS", "0")),
    }


# -------------------------------------------------------------------
# Optionnel: préchauffe le cache (pour éviter 100% remote au premier run)
# -------------------------------------------------------------------
async def warmup_cache(exchange: BitgetExchange, symbols: list[str], tf: str, limit: int) -> None:
    for s in symbols:
        try:
            await exchange.fetch_ohlcv(s, tf, limit)
            print(f"[cache] warmup OK for {s}")
        except Exception as e:  # noqa: BLE001
            print(f"[cache] warmup FAIL for {s}: {e}")


# -------------------------------------------------------------------
async def main() -> None:
    ensure_ccxt()

    cfg = load_run_config()

    # Instancie Bitget (spot + cache)
    ex = BitgetExchange(
        api_key=os.environ.get("BITGET_API_KEY"),
        secret=os.environ.get("BITGET_API_SECRET"),
        password=os.environ.get("BITGET_API_PASSPHRASE"),
        data_dir=cfg["DATA_DIR"],
        use_cache=cfg["USE_CACHE"],
        min_fresh_seconds=cfg["CACHE_MIN_FRESH_SECONDS"],
        spot=True,  # on reste en spot pour l’instant
    )

    # Pré-chargement cache (rapide; safe si déjà présent)
    await warmup_cache(ex, cfg["TOP_SYMBOLS"], cfg["TIMEFRAME"], cfg["FETCH_LIMIT"])

    # Lance orchestrateur (notifier/commands construit dedans)
    try:
        await run_orchestrator(ex, cfg)
    finally:
        await ex.close()


if __name__ == "__main__":
    asyncio.run(main())