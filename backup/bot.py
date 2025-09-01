from __future__ import annotations
import os, logging
from typing import List
from engine.pipeline.runner import PipelineScheduler
from tools.load_pairs import load_pairs

def _env_list(name: str, default: List[str]) -> List[str]:
    raw = os.getenv(name, "")
    vals = [x.strip() for x in raw.split(",") if x.strip()]
    return vals or default

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    tfs = _env_list("SCALP_TFS", ["1m","5m","15m"])
    symbols = load_pairs()  # top 5 au démarrage, puis runner rechargera auto

    interval = float(os.getenv("SCALP_INTERVAL_SEC", "5"))
    reload_pairs_sec = float(os.getenv("SCALP_RELOAD_PAIRS_SEC", "60"))

    sched = PipelineScheduler(
        symbols=symbols,
        tfs=tfs,
        interval_sec=interval,
        reload_pairs_sec=reload_pairs_sec,
        logger=logging.getLogger("bot"),
    )
    sched.run()
