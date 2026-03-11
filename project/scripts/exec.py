#!/usr/bin/env python3

import sqlite3
import time
from pathlib import Path

ROOT = Path("/opt/scalp/project")

DB_EXEC = ROOT / "data/exec.db"
DB_TICK = ROOT / "data/t.db"

SQL_INGEST = ROOT / "sql/exec_ingest.sql"

LOOP_SLEEP = 0.2
FEE_PCT = 0.0006


def conn(db):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    return c


def ingest():

    with conn(DB_EXEC) as db:
        db.executescript(SQL_INGEST.read_text())


def get_price(instId):

    with conn(DB_TICK) as t:

        r = t.execute("""
        SELECT lastPr
        FROM v_ticks_latest
        WHERE instId=?
        LIMIT 1
        """,(instId,)).fetchone()

        if not r:
            return None

        px = float(r["lastPr"])

        if px <= 0:
            return None

        return px


def execute_orders():

    with conn(DB_EXEC) as db:

        rows = db.execute("""
        SELECT *
        FROM exec
        WHERE status='exec_req'
        """).fetchall()

        for r in rows:

            price = get_price(r["instId"])

            if price is None:
                continue

            fee = abs(r["qty"] * price) * FEE_PCT

            db.execute("""
            UPDATE exec
            SET status='done',
                price_exec=?,
                fee=?,
                ts_exec=strftime('%s','now')*1000
            WHERE exec_id=?
            """,(price,fee,r["exec_id"]))

        db.commit()


def main():

    while True:

        ingest()

        execute_orders()

        time.sleep(LOOP_SLEEP)


if __name__ == "__main__":
    main()
