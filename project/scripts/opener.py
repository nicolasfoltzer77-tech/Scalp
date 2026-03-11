#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import time
from pathlib import Path
import logging

ROOT = Path("/opt/scalp/project")

DB_GEST   = ROOT / "data/gest.db"
DB_OPENER = ROOT / "data/opener.db"

SQL_INGEST = ROOT / "sql/opener_ingest.sql"
SQL_ACK    = ROOT / "sql/opener_ack_exec.sql"

LOOP_SLEEP = 0.2

# =========================================
# LOG
# =========================================

LOG = ROOT / "logs/opener.log"

logging.basicConfig(
    filename=str(LOG),
    level=logging.INFO,
    format="%(asctime)s OPENER %(levelname)s %(message)s"
)

log = logging.getLogger("OPENER")


# =========================================
# DB
# =========================================

def conn(db):

    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row

    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")

    return c


# =========================================
# INGEST GEST -> OPENER
# =========================================

def ingest():

    try:

        with conn(DB_OPENER) as o:

            o.executescript(SQL_INGEST.read_text())

    except Exception:
        log.exception("[ERR] ingest")


# =========================================
# ACK EXEC -> OPENER
# =========================================

def ack_exec():

    try:

        with conn(DB_OPENER) as o:

            o.executescript(SQL_ACK.read_text())

    except Exception:
        log.exception("[ERR] ack_exec")


# =========================================
# MAIN LOOP
# =========================================

def main():

    log.info("[START] opener")

    while True:

        ack_exec()

        ingest()

        time.sleep(LOOP_SLEEP)


if __name__ == "__main__":
    main()
