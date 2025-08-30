import os
import time
import logging

from engine.pipeline.runner import PipelineScheduler
from engine.strategies.runner import load_strategies

# --- Logging setup ---
LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LEVEL, logging.INFO),
                    format="%(asctime)s | %(levelname)s | %(message)s")
LOG = logging.getLogger("bot")

# --- Charger stratégies ---
_STRATS, _CFG = load_strategies()


def main():
    symbols = ["BTCUSDT", "ETHUSDT"]
    tfs = ["1m", "5m", "15m"]

    LOG.info("Bot démarré avec %s / %s", symbols, tfs)

    sched = PipelineScheduler(symbols=symbols,
                              tfs=tfs,
                              strategies=_STRATS,
                              config=_CFG,
                              logger=LOG)

    # Boucle infinie
    while True:
        try:
            sched.run_once()
        except Exception:
            LOG.exception("pipeline task error")
        time.sleep(5)


if __name__ == "__main__":
    main()
