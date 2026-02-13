#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
UPGRADE SÉCURITÉ FSM

Si opener_from_exec plante, on garantit quand même :

exec(done) → opener(open_done / pyramide_done)
exec(done) → closer(partial_done / close_done)

AUCUN impact si l'ancien système marche.
Simple filet de sécurité.
"""

import sqlite3
from pathlib import Path

ROOT = Path("/opt/scalp/project")
DB_EXEC   = ROOT / "data/exec.db"
DB_OPENER = ROOT / "data/opener.db"
DB_CLOSER = ROOT / "data/closer.db"


def conn(db):
    c = sqlite3.connect(str(db), timeout=5)
    c.row_factory = sqlite3.Row
    return c


def run():
    e = conn(DB_EXEC)
    o = conn(DB_OPENER)
    c = conn(DB_CLOSER)

    # ---------- OPENER ACK ----------
    rows = e.execute("""
        SELECT uid, exec_type, step
        FROM exec
        WHERE status='done'
    """).fetchall()

    for r in rows:
        uid  = r["uid"]
        et   = r["exec_type"]
        step = r["step"]

        if et == "open":
            o.execute("""
                UPDATE opener
                SET status='open_done'
                WHERE uid=? AND step=? AND status='open_stdby'
            """, (uid, step))

        elif et == "pyramide":
            o.execute("""
                UPDATE opener
                SET status='pyramide_done'
                WHERE uid=? AND step=? AND status='pyramide_stdby'
            """, (uid, step))

        elif et == "partial":
            c.execute("""
                UPDATE closer
                SET status='partial_done'
                WHERE uid=? AND step=? AND status='partial_stdby'
            """, (uid, step))

        elif et == "close":
            c.execute("""
                UPDATE closer
                SET status='close_done'
                WHERE uid=? AND step=? AND status='close_stdby'
            """, (uid, step))

    o.commit()
    c.commit()
    e.close(); o.close(); c.close()


if __name__ == "__main__":
    run()

