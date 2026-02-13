#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GEST — TRIGGERS → OPEN_REQ
Ajoute les nouveaux trades dans GEST
Ne touche PAS aux transitions FSM
"""

import sqlite3
from pathlib import Path

ROOT = Path("/opt/scalp/project")
DB_TRIG = ROOT / "data/triggers.db"
DB_GEST = ROOT / "data/gest.db"

def conn(db):
    c = sqlite3.connect(str(db), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c

def ingest():
    t = conn(DB_TRIG)
    g = conn(DB_GEST)

    rows = t.execute("""
        SELECT uid, instId, side, price, score_C
        FROM triggers
        WHERE status='fired'
    """).fetchall()

    for r in rows:
        if g.execute("SELECT 1 FROM gest WHERE uid=?", (r["uid"],)).fetchone():
            continue

        g.execute("""
            INSERT INTO gest (uid, instId, side, entry, price_signal, score_C, status)
            VALUES (?, ?, ?, ?, ?, ?, 'open_req')
        """, (
            r["uid"],
            r["instId"],
            r["side"],
            r["price"],
            r["price"],
            r["score_C"]
        ))

    g.commit()
    t.close()
    g.close()

if __name__ == "__main__":
    ingest()

