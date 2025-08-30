from __future__ import annotations
import os, logging
from typing import List
from engine.pipeline.runner import PipelineScheduler

def _env_list(name: str, default: List[str]) -> List[str]:
    raw = os.getenv(name, "")
    vals = [x.strip() for x in raw.split(",") if x.strip()]
    return vals or default

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    symbols = _env_list("SCALP_SYMBOLS", ["BTCUSDT", "ETHUSDT"])
    tfs     = _env_list("SCALP_TFS", ["1m", "5m", "15m"])
    sched = PipelineScheduler(symbols=symbols, tfs=tfs, interval=5.0, logger=logging.getLogger())
    sched.run()

