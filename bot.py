# -*- coding: utf-8 -*-
from __future__ import annotations
import asyncio
import os
import sys
from pathlib import Path

# 0) charge .env parent si présent (cas Paperspace: .env à côté du dossier scalp/)
PARENT_ENV = Path(__file__).resolve().parent.parent / ".env"
if PARENT_ENV.exists():
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv(PARENT_ENV)
    except Exception:
        pass

# 1) imports projet
from scalper.live import RunConfig, run_orchestrator
from scalper.live.notify import build_notifier_and_commands


async def main() -> None:
    # Config minimale : watchlist 10 paires @ 5m, refresh 30s
    cfg = RunConfig(
        symbols=[
            "BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT",
            "DOGEUSDT","ADAUSDT","LTCUSDT","AVAXUSDT","LINKUSDT"
        ],
        timeframe="5m",
        refresh_secs=30.0,
        cache_dir="/notebooks/data"
    )

    notifier, _commands = await build_notifier_and_commands({})
    await run_orchestrator(cfg, notifier, cache_dir_factory=lambda: "/notebooks/data")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass