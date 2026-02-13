#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DEC TICKS WRITER — FINAL

- lit instId_s depuis t.db.v_ticks_latest
- copie strictement dans dec.db.snap_ticks
"""

import sqlite3
from pathlib import Path

ROOT = Path("/opt/scalp/project")
DB_TICKS = ROOT / "data/t.db"
DB_DEC   = ROOT / "data/dec.db"

def conn(p):
    c = sqlite3.connect(str(p))
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    return c

def main():
    ct = conn(DB_TICKS)
    cd = conn(DB_DEC)

    rows = ct.execute("""
        SELECT instId_s, lastPr, ts_ms
        FROM v_ticks_latest
    """).fetchall()

    cd.executemany("""
        INSERT OR REPLACE INTO snap_ticks
        (instId_s, lastPr, ts)
        VALUES (?, ?, ?)
    """, [
        (r["instId_s"], r["lastPr"], r["ts_ms"])
        for r in rows
    ])

    cd.commit()
    ct.close()
    cd.close()

if __name__ == "__main__":
    main()

