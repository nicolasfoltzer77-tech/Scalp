#!/usr/bin/env python3
import sqlite3
import time
from pathlib import Path

ROOT = Path("/opt/scalp/project")
DB_TICKS = ROOT / "data/t.db"
DB_DEC   = ROOT / "data/dec.db"

SLEEP = 0.25

def conn(db):
    c = sqlite3.connect(str(db), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    return c

while True:
    with conn(DB_TICKS) as t, conn(DB_DEC) as d:
        rows = t.execute("""
            SELECT instId, lastPr, ts_ms
            FROM v_ticks_latest
        """).fetchall()

        d.executemany("""
            INSERT INTO ticks_live(instId,lastPr,ts_ms)
            VALUES(?,?,?)
            ON CONFLICT(instId) DO UPDATE SET
              lastPr=excluded.lastPr,
              ts_ms =excluded.ts_ms
        """, [(r["instId"], r["lastPr"], r["ts_ms"]) for r in rows])

    time.sleep(SLEEP)

