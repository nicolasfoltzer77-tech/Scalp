#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import time
import logging
from pathlib import Path

ROOT = Path("/opt/scalp/project")
DB_GEST   = ROOT / "data/gest.db"
DB_CLOSER = ROOT / "data/closer.db"

log = logging.getLogger("GEST")

def conn(db):
    c = sqlite3.connect(str(db), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c

def now_ms():
    return int(time.time() * 1000)

def copy_closer():
    g = conn(DB_GEST)
    c = conn(DB_CLOSER)
    now = now_ms()

    for r in c.execute("""
        SELECT uid, status, ts_exec
        FROM closer
        WHERE status IN ('partial_done','close_done')
    """):
        if r["status"] == "partial_done":
            g.execute("""
                UPDATE gest
                SET status='partial_done',
                    ts_close=?,
                    ts_updated=?
                WHERE uid=? AND status IN ('partial_req','close_req')
            """, (r["ts_exec"], now, r["uid"]))

        elif r["status"] == "close_done":
            g.execute("""
                UPDATE gest
                SET status='close_done',
                    ts_close=?,
                    ts_updated=?
                WHERE uid=? AND status='close_req'
            """, (r["ts_exec"], now, r["uid"]))

    g.commit()
    g.close()
    c.close()

