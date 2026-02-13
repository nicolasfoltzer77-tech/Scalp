#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import time
import logging
from pathlib import Path

ROOT = Path("/opt/scalp/project")
DB_GEST   = ROOT / "data/gest.db"
DB_FOLLOW = ROOT / "data/follower.db"

log = logging.getLogger("GEST")

def conn(db):
    c = sqlite3.connect(str(db), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c

def now_ms():
    return int(time.time() * 1000)

def sync_follow_state():
    g = conn(DB_GEST)
    f = conn(DB_FOLLOW)
    now = now_ms()

    rows = g.execute("""
        SELECT uid, status
        FROM gest
        WHERE status IN ('open_done','partial_done','pyramide_done')
    """).fetchall()

    for r in rows:
        uid = r["uid"]

        fr = f.execute("""
            SELECT status FROM follower WHERE uid=?
        """, (uid,)).fetchone()

        if not fr:
            continue

        if fr["status"] == "follow":
            g.execute("""
                UPDATE gest
                SET status='follow',
                    ts_updated=?
                WHERE uid=? AND status=?
            """, (now, uid, r["status"]))

            log.info("[GEST FOLLOW] %s %s -> follow", uid, r["status"])

    g.commit()
    g.close()
    f.close()

