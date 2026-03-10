#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCALP DEC WRITER
Tick-driven engine
Reads ticks from t.db
Writes analytics into dec.db
Robust logging (file + systemd journal)
"""

import time
import logging
import sys
import sqlite3
from pathlib import Path

from dec_atr import refresh_snap_atr
from dec_range import refresh_snap_range
from dec_range_ext import refresh_snap_range_ext
from dec_signal import refresh_signal_history
from dec_cluster import refresh_cluster_history


ROOT = Path("/opt/scalp/project")

DB_TICKS = ROOT / "data/t.db"
DB_DEC   = ROOT / "data/dec.db"

LOG_PATH = ROOT / "logs/dec_writer.log"

BASE_SLEEP = 0.15
HEARTBEAT_MS = 10000


# ------------------------------
# Logging setup (file + journal)
# ------------------------------

logger = logging.getLogger("DEC")
logger.setLevel(logging.INFO)

fmt = logging.Formatter("%(asctime)s DEC %(levelname)s %(message)s")

# file log
fh = logging.FileHandler(LOG_PATH)
fh.setFormatter(fmt)
logger.addHandler(fh)

# stdout log (systemd journal)
sh = logging.StreamHandler(sys.stdout)
sh.setFormatter(fmt)
logger.addHandler(sh)

log = logger


# ------------------------------
# DB connection
# ------------------------------

def conn_ticks():
    c = sqlite3.connect(str(DB_TICKS), timeout=5)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    return c


def latest_tick_ts():

    try:
        with conn_ticks() as c:
            r = c.execute(
                "SELECT MAX(ts_ms) AS ts FROM ticks"
            ).fetchone()

        return int(r["ts"] or 0)

    except Exception:
        log.exception("[TICK_READ_ERROR]")
        return 0


# ------------------------------
# Main loop
# ------------------------------

def main():

    log.info("[BOOT] dec_writer started")
    print("dec_writer started", flush=True)

    last_tick = 0
    last_atr = 0
    last_signal = 0
    last_range = 0
    last_heartbeat = 0

    while True:

        try:

            tick_ts = latest_tick_ts()
            now = int(time.time() * 1000)

            # heartbeat log
            if now - last_heartbeat > HEARTBEAT_MS:
                log.info("[HEARTBEAT] tick=%s", tick_ts)
                last_heartbeat = now

            # wait for new tick
            if tick_ts <= last_tick:
                time.sleep(BASE_SLEEP)
                continue

            last_tick = tick_ts

            atr_rows = 0
            signal_rows = 0
            range_rows = 0
            ext_rows = 0
            cluster_rows = 0

            # ATR update
            if now - last_atr > 1000:
                atr_rows = refresh_snap_atr()
                last_atr = now

            # signal update
            if now - last_signal > 2000:
                signal_rows = refresh_signal_history()
                last_signal = now

            # range / cluster update
            if now - last_range > 45000:

                stats = refresh_snap_range()
                range_rows = stats.get("rows", 0)

                ext_rows = refresh_snap_range_ext()
                cluster_rows = refresh_cluster_history()

                last_range = now

            log.info(
                "[DEC] tick=%d atr=%d signal=%d range=%d ext=%d cluster=%d",
                tick_ts,
                atr_rows,
                signal_rows,
                range_rows,
                ext_rows,
                cluster_rows
            )

        except Exception:
            log.exception("[DEC_RUNTIME_ERROR]")

        time.sleep(BASE_SLEEP)


if __name__ == "__main__":
    main()
