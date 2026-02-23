#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GEST — INGEST TRIGGERS → OPEN_REQ

RÈGLES :
- lecture STRICTE du schéma triggers
- aucun champ fantôme
- aucun calcul
"""

import sqlite3
import logging
from pathlib import Path

ROOT = Path("/opt/scalp/project")

DB_TRIG = ROOT / "data/triggers.db"
DB_GEST = ROOT / "data/gest.db"

LOG = ROOT / "logs/gest.log"
log = logging.getLogger("GEST")

# ============================================================
# UTILS
# ============================================================

def now_ms():
    import time
    return int(time.time() * 1000)

def conn(db):
    c = sqlite3.connect(str(db), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c

def rget(row, k, d=None):
    try:
        return row[k]
    except Exception:
        return d

# ============================================================
# INGEST
# ============================================================

def ingest_triggers():
    t = conn(DB_TRIG)
    g = conn(DB_GEST)
    now = now_ms()

    rows = list(t.execute("""
        SELECT *
        FROM triggers
        WHERE status='fire'
    """))

    if rows:
        log.info("[INGEST] %d triggers fired", len(rows))

    for r in rows:
        uid = rget(r, "uid")
        if not uid:
            continue

        # déjà ingéré
        if g.execute("SELECT 1 FROM gest WHERE uid=?", (uid,)).fetchone():
            continue

        g.execute("""
            INSERT INTO gest (
                uid, instId, side,

                ts_signal,
                price_signal,
                atr_signal,

                reason,
                entry_reason,
                type_signal,

                score_of,
                score_mo,
                score_br,
                score_force,

                dec_mode,
                dec_score_C,
                dec_ctx,

                status,
                step,
                ts_created,
                ts_updated
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            uid,
            rget(r,"instId"),
            rget(r,"side"),

            rget(r,"ts"),
            rget(r,"price"),
            rget(r,"atr"),

            rget(r,"fire_reason"),
            rget(r,"entry_reason"),
            rget(r,"trigger_type"),

            rget(r,"score_of"),
            rget(r,"score_mo"),
            rget(r,"score_br"),
            rget(r,"score_force"),

            rget(r,"dec_mode"),
            rget(r,"dec_score_C"),
            rget(r,"ctx"),

            "open_stdby",
            0,
            now,
            now
        ))

        log.info("[OPEN_REQ] %s (%s)", uid, rget(r,"instId"))

    g.commit()
    t.close()
    g.close()


