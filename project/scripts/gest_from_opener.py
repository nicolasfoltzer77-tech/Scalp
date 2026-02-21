#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import time
import logging
from pathlib import Path

ROOT = Path("/opt/scalp/project")
DB_GEST   = ROOT / "data/gest.db"
DB_OPENER = ROOT / "data/opener.db"

log = logging.getLogger("GEST")

def conn(db):
    c = sqlite3.connect(str(db), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c

def now_ms():
    return int(time.time() * 1000)

def copy_opener():
    g = conn(DB_GEST)
    o = conn(DB_OPENER)
    now = now_ms()

    for r in o.execute("""
        SELECT uid, status, step, price_exec_open, ts_open
        FROM opener
        WHERE status IN ('open_done','pyramide_done')
    """):
        if r["status"] == "open_done":
            g.execute("""
                UPDATE gest
                SET status='open_done',
                    step=?,
                    entry=?,
                    ts_open=?,
                    ts_updated=?
                WHERE uid=? AND status='open_req'
            """, (r["step"], r["price_exec_open"], r["ts_open"], now, r["uid"]))

        elif r["status"] == "pyramide_done":
            g.execute("""
                UPDATE gest
                SET status='pyramide_done',
                    step=?,
                    ts_updated=?
                WHERE uid=? AND status='pyramide_req'
            """, (r["step"], now, r["uid"]))

    g.commit()
    g.close()
    o.close()

