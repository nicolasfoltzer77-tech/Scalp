#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
OPENER — PYRAMIDE INGEST (FSM SAFE)
Consomme UNIQUEMENT gest.status = pyramide_req
Indexé STRICTEMENT sur gest.step
"""

import sqlite3
import logging
from pathlib import Path

ROOT = Path("/opt/scalp/project")

DB_GEST   = ROOT / "data/gest.db"
DB_OPENER = ROOT / "data/opener.db"

log = logging.getLogger("OPENER")

def conn(db):
    c = sqlite3.connect(str(db), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c

def ingest_pyramide():
    g = conn(DB_GEST)
    o = conn(DB_OPENER)

    for r in g.execute("""
        SELECT uid, instId, side, qty_to_close, step
        FROM gest
        WHERE status='pyramide_req'
    """):
        uid  = r["uid"]
        qty  = float(r["qty_to_close"] or 0.0)
        step = int(r["step"])

        if qty <= 0:
            continue

        # 🔒 VERROU FSM STRICT
        if o.execute("""
            SELECT 1 FROM opener
            WHERE uid=? AND exec_type='pyramide' AND step=?
        """, (uid, step)).fetchone():
            continue

        o.execute("""
            INSERT INTO opener
            (uid, instId, side, qty, lev, status, exec_type, step)
            VALUES (?,?,?,?,1,'open_stdby','pyramide',?)
        """, (
            uid,
            r["instId"],
            r["side"],
            qty,
            step
        ))

        log.info("[PYRAMIDE_STDBY] %s step=%d qty=%.6f", uid, step, qty)

    o.commit()
    g.close()
    o.close()

