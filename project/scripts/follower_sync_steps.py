#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FOLLOWER — SYNC done_step FROM exec.db

- done_step écrit uniquement ici côté follower (lecture exec)
- exec est source de vérité : max(done_step) par uid
- ne modifie pas req_step
"""

import sqlite3
from pathlib import Path

ROOT = Path("/opt/scalp/project")
DB_EXEC = ROOT / "data/exec.db"
DB_FOLLOWER = ROOT / "data/follower.db"

def conn(db):
    c = sqlite3.connect(str(db), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA busy_timeout=10000;")
    return c

def sync_done_steps(*, f):
    """
    f : sqlite connection follower.db (writer loop)
    """
    e = conn(DB_EXEC)

    rows = e.execute("""
        SELECT uid, MAX(COALESCE(done_step, step)) AS done_step
        FROM exec
        WHERE status='done'
        GROUP BY uid
    """).fetchall()

    for r in rows:
        f.execute("""
            UPDATE follower
            SET done_step=?
            WHERE uid=?
        """, (int(r["done_step"] or 0), r["uid"]))

    e.close()

