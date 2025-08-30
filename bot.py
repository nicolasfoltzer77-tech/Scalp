#!/usr/bin/env python3
"""
Scalp Bot (multi-pipelines + GitHub Pages)
"""

import os
import time
import logging

from engine.pipeline.runner import PipelineScheduler

LOG = logging.getLogger("bot")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s | %(message)s",
)

if __name__ == "__main__":
    symbols = os.environ.get("SCALP_SYMBOLS", "BTCUSDT,ETHUSDT").split(",")
    tfs = os.environ.get("SCALP_TFS", "1m,5m,15m").split(",")

    scheduler = PipelineScheduler(symbols, tfs, interval=30, logger=LOG)
    LOG.info("bootstrap symbols=%s tfs=%s", symbols, tfs)
    scheduler.run_forever()
