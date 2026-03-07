#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GEST — TRIGGERS → OPEN_REQ
Ajoute les nouveaux trades dans GEST
Ne touche PAS aux transitions FSM
"""

import sqlite3
from pathlib import Path

from db_utils import ensure_column

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

    for col, typ in (
        ("trigger_strength", "REAL"),
        ("trigger_age_ms", "INTEGER"),
        ("trigger_distance_atr", "REAL"),
        ("spread_entry", "REAL"),
        ("signal_age_ms", "INTEGER"),
    ):
        ensure_column(t, "triggers", col, typ)

    for col, typ in (
        ("trigger_strength", "REAL"),
        ("trigger_age_ms", "INTEGER"),
        ("trigger_distance_atr", "REAL"),
        ("spread_entry", "REAL"),
        ("signal_age_ms", "INTEGER"),
    ):
        ensure_column(g, "gest", col, typ)

    rows = t.execute(
        """
        SELECT uid, instId, side, price, score_C,
               trigger_strength, trigger_age_ms, trigger_distance_atr,
               spread_entry, signal_age_ms
        FROM triggers
        WHERE status='fire'
    """
    ).fetchall()

    for r in rows:
        if g.execute("SELECT 1 FROM gest WHERE uid=?", (r["uid"],)).fetchone():
            continue

        g.execute(
            """
            INSERT INTO gest (
                uid, instId, side, entry, price_signal, score_C, status,
                trigger_strength, trigger_age_ms, trigger_distance_atr,
                spread_entry, signal_age_ms
            )
            VALUES (?, ?, ?, ?, ?, ?, 'open_stdby', ?, ?, ?, ?, ?)
        """,
            (
                r["uid"],
                r["instId"],
                r["side"],
                r["price"],
                r["price"],
                r["score_C"],
                r["trigger_strength"],
                r["trigger_age_ms"],
                r["trigger_distance_atr"],
                r["spread_entry"],
                r["signal_age_ms"],
            ),
        )

    g.commit()
    t.close()
    g.close()


if __name__ == "__main__":
    ingest()
