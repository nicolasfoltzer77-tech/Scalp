#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GEST — PURGE FINALE
Purge UID uniquement quand recorder.status='Recorded' (tolère 'recorded').
"""

import sqlite3
import logging
from pathlib import Path

ROOT = Path("/opt/scalp/project")

DB_GEST     = ROOT / "data/gest.db"
DB_RECORDER = ROOT / "data/recorder.db"

log = logging.getLogger("GEST")


def conn(db):
    c = sqlite3.connect(str(db), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c


def purge_recorded():
    g = conn(DB_GEST)
    r = conn(DB_RECORDER)

    try:
        rows = r.execute("""
            SELECT DISTINCT uid
            FROM recorder
            WHERE lower(coalesce(status, ''))='recorded'
        """).fetchall()

        for x in rows:
            if g.execute("DELETE FROM gest WHERE uid=?", (x["uid"],)).rowcount:
                log.info("[PURGE] %s", x["uid"])

        g.commit()
    finally:
        g.close()
        r.close()
