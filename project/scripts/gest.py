#!/usr/bin/env python3

import sqlite3
import time
from pathlib import Path

ROOT = Path("/opt/scalp/project")

DB_GEST = ROOT / "data/gest.db"
SQL_ENGINE = ROOT / "sql/gest_engine.sql"

LOOP_SLEEP = 0.2


def conn():
    c = sqlite3.connect(DB_GEST, timeout=10)
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA synchronous=NORMAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c


def run_cycle():
    with conn() as db:
        sql = SQL_ENGINE.read_text()
        db.executescript(sql)


def main():

    while True:
        try:
            run_cycle()
        except Exception as e:
            print("GEST ERROR:", e)

        time.sleep(LOOP_SLEEP)


if __name__ == "__main__":
    main()

