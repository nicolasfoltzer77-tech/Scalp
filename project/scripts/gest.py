#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import time
import logging
from pathlib import Path

ROOT = Path("/opt/scalp/project")

DB_GEST = ROOT / "data/gest.db"

SQL_TRIG  = ROOT / "sql/gest_ingest_triggers.sql"
SQL_MARK  = ROOT / "sql/gest_mark_triggers_ingested.sql"
SQL_ACK   = ROOT / "sql/gest_ack_opener.sql"
SQL_FOLL  = ROOT / "sql/gest_follow_actions.sql"

LOOP_SLEEP = 0.2

LOG = ROOT / "logs/gest.log"

logging.basicConfig(
    filename=str(LOG),
    level=logging.INFO,
    format="%(asctime)s GEST %(levelname)s %(message)s",
    force=True
)

log = logging.getLogger("GEST")


# -----------------------------------------
# DB connection
# -----------------------------------------

def conn():

    c = sqlite3.connect(DB_GEST, timeout=10)

    c.row_factory = sqlite3.Row

    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")

    return c


# -----------------------------------------
# Load SQL once
# -----------------------------------------

def load_sql():

    sql = {}

    if SQL_TRIG.exists():
        sql["trig"] = SQL_TRIG.read_text()

    if SQL_MARK.exists():
        sql["mark"] = SQL_MARK.read_text()

    if SQL_ACK.exists():
        sql["ack"] = SQL_ACK.read_text()

    if SQL_FOLL.exists():
        sql["foll"] = SQL_FOLL.read_text()

    return sql


# -----------------------------------------
# MAIN LOOP
# -----------------------------------------

def main():

    log.info("[START] gest")

    sql = load_sql()

    g = conn()

    while True:

        try:

            if "trig" in sql:
                g.executescript(sql["trig"])

            if "mark" in sql:
                g.executescript(sql["mark"])

            if "ack" in sql:
                g.executescript(sql["ack"])

            if "foll" in sql:
                g.executescript(sql["foll"])

        except Exception:

            log.exception("[ERR] gest loop")

        time.sleep(LOOP_SLEEP)


if __name__ == "__main__":
    main()

