from __future__ import annotations
import os, json, logging
from typing import List
from engine.pipeline.runner import PipelineScheduler

LOG = logging.getLogger("bot")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

REPO_PATH = os.getenv("REPO_PATH", "/opt/scalp")
REPORTS = os.path.join(REPO_PATH, "reports")
WATCHLIST = os.path.join(REPORTS, "watchlist.json")

# TFS via env: LIVE_TFS="1m,5m,15m" (compat LIVE_TF)
LIVE_TFS = os.getenv("LIVE_TFS", os.getenv("LIVE_TF", "1m,5m,15m"))
TFS: List[str] = [t.strip() for t in LIVE_TFS.split(",") if t.strip()]

# Concurrence & intervalle
MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "6"))
INTERVAL_SEC = int(os.getenv("PIPELINE_INTERVAL_SEC", "5"))

# Fallback manuel si watchlist absente
MANUAL_SYMBOLS = os.getenv("MANUAL_SYMBOLS", '["BTCUSDT","ETHUSDT","DOGEUSDT"]').strip()

def read_watchlist_symbols() -> List[str]:
    """Lit la watchlist, filtre *USDT, sinon fallback manuel."""
    try:
        with open(WATCHLIST, "r") as f:
            data = json.load(f)
        syms = data.get("symbols") or []
        syms = [s for s in syms if s.endswith("USDT")]
        if syms:
            LOG.info("[bot] using watchlist symbols: %s", syms)
            return syms
    except Exception as e:
        LOG.warning("watchlist read failed: %s", e)
    try:
        syms = json.loads(MANUAL_SYMBOLS)
    except Exception:
        syms = ["BTCUSDT", "ETHUSDT"]
    LOG.info("[bot] fallback symbols: %s", syms)
    return syms

def main():
    symbols = read_watchlist_symbols()
    LOG.info(
        "[bot] bootstrap symbols=%s tfs=%s max_concurrency=%s",
        symbols, TFS, MAX_CONCURRENCY
    )
    sched = PipelineScheduler(
        symbols=symbols,
        tfs=TFS,
        interval=INTERVAL_SEC,
        max_workers=MAX_CONCURRENCY,
        logger=LOG,
    )
    sched.start()

if __name__ == "__main__":
    main()
