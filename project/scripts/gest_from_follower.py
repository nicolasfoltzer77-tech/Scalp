#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3, time
from pathlib import Path

ROOT = Path("/opt/scalp/project")
DB_GEST = ROOT / "data/gest.db"
DB_FOLLOWER = ROOT / "data/follower.db"

def conn(db):
    c = sqlite3.connect(str(db), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    return c

def now_ms(): return int(time.time()*1000)

def loop():
    f = conn(DB_FOLLOWER)
    g = conn(DB_GEST)
    now = now_ms()

    for fr in f.execute("SELECT * FROM follower"):

        g.execute("""
        INSERT INTO gest (uid, instId, side, status, step,
                          ratio_to_close, ratio_to_add, ts_updated)
        VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(uid) DO UPDATE SET
            status=excluded.status,
            step=excluded.step,
            ratio_to_close=excluded.ratio_to_close,
            ratio_to_add=excluded.ratio_to_add,
            ts_updated=excluded.ts_updated
        """, (
            fr["uid"],
            fr["instId"],
            fr["side"],
            fr["status"],
            fr["req_step"],
            fr["qty_to_close_ratio"],   -- ✅ LE BON CHAMP
            fr["qty_to_add_ratio"],
            now
        ))

    g.commit()
    f.close(); g.close()

if __name__ == "__main__":
    while True:
        loop()
        time.sleep(0.25)

