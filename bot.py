# /opt/scalp/bot.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, time, json, pathlib, logging, subprocess, shlex

from engine.watchlist import load_watchlist
from engine.strategies.runner import load_strategies
from engine.pipeline.runner import PipelineScheduler

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(message)s",
)
LOG = logging.getLogger("scalp-bot")

HEARTBEAT = pathlib.Path("/opt/scalp/reports/heartbeat.json")

def _start_backfill_worker_if_present():
    worker = "/opt/scalp/jobs/backfill_worker.py"
    if os.path.exists(worker):
        try:
            subprocess.Popen([os.environ.get("PYTHON_BIN", "/opt/scalp/venv/bin/python"), worker],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            LOG.info("starting backfill worker (delayed)")
        except Exception as e:
            LOG.warning(f"backfill worker absent: {e}")
    else:
        LOG.info("backfill worker not found, skipping")

def write_heartbeat(extra: dict = None):
    HEARTBEAT.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ts": int(time.time()*1000)}
    if extra: payload.update(extra)
    HEARTBEAT.write_text(json.dumps(payload))

def main():
    LOG.info("[bot] starting")
    load_strategies()  # charge les stratégies
    wl = load_watchlist()
    symbols, tfs = wl["symbols"], wl["tfs"]
    LOG.info(f"[bot] bootstrap symbols: {symbols}  tfs: {tfs}")
    LOG.info("using watchlist symbols at startup")

    sched = PipelineScheduler()
    LOG.info(f"max_concurrency={sched.max_concurrency}")

    _start_backfill_worker_if_present()

    # Boucle infinie
    while True:
        write_heartbeat({"symbols": symbols, "tfs": tfs})
        try:
            sched.run_cycle(symbols, tfs)
        except Exception as e:
            LOG.exception(f"run_cycle error: {e}")
        time.sleep(5)

if __name__ == "__main__":
    main()
