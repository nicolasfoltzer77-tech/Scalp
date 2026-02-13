#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FOLLOWER — INGEST OPEN_DONE
SOURCE UNIQUE : gest.db
RÔLE :
- créer la ligne follower à open_done
- NE JAMAIS updater une ligne inexistante
"""

def ingest_open_done(g, f, now):
    """
    g : sqlite gest (READ)
    f : sqlite follower (WRITE)
    now : timestamp ms
    """

    rows = g.execute("""
        SELECT
            uid,
            instId,
            side,
            step,
            ts_open,
            entry,
            qty,
            lev
        FROM gest
        WHERE status='open_done'
    """).fetchall()

    if not rows:
        return

    for r in rows:
        uid = r["uid"]

        # 🔒 Verrou absolu : follower déjà créé ?
        exists = f.execute("""
            SELECT 1 FROM follower WHERE uid=?
        """, (uid,)).fetchone()

        if exists:
            continue

        f.execute("""
            INSERT INTO follower (
                uid,
                instId,
                side,
                step,
                status,
                ts_follow,
                last_action_ts,
                qty_ratio,
                nb_partial,
                nb_pyramide
            ) VALUES (
                ?,?,?,?,?,?,?,?,?,?
            )
        """, (
            uid,
            r["instId"],
            r["side"],
            r["step"] or 0,
            "follow",
            now,
            now,
            1.0,
            0,
            0
        ))

