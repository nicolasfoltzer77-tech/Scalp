#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FSM ACK — exec -> opener

Règle :
- exec termine le step N
- exec.step est déjà passé à N+1
- opener ACK sur le step N = exec.step - 1
"""

import sqlite3
from pathlib import Path
import logging

log = logging.getLogger("OPENER_ACK")

ROOT = Path("/opt/scalp/project")
DB_EXEC   = ROOT / "data/exec.db"
DB_OPENER = ROOT / "data/opener.db"


def conn(db):
    c = sqlite3.connect(str(db), timeout=5)
    c.row_factory = sqlite3.Row
    return c


def _ack_open_done():
    e = conn(DB_EXEC)
    o = conn(DB_OPENER)

    try:
        rows = e.execute("""
            SELECT uid, exec_type, step
            FROM exec
            WHERE status='done'
              AND exec_type='open'
        """).fetchall()

        for r in rows:
            uid       = r["uid"]
            step_done = int(r["step"]) - 1

            if step_done < 0:
                continue

            res = o.execute("""
                UPDATE opener
                SET status='open_done'
                WHERE uid=?
                  AND exec_type='open'
                  AND step=?
                  AND status='open_stdby'
            """, (uid, step_done))

            if res.rowcount:
                log.info("[ACK] open_done uid=%s step=%s", uid, step_done)

        o.commit()

    except Exception:
        log.exception("[ERR] opener_from_exec")
        try:
            o.rollback()
        except Exception:
            pass
    finally:
        e.close()
        o.close()


# ==================================================
# API COMPAT — DO NOT REMOVE
# ==================================================
def ingest_exec_done():
    """
    API historique attendue par opener.py
    NE PAS SUPPRIMER
    """
    _ack_open_done()


# ==================================================
# CLI
# ==================================================
if __name__ == "__main__":
    ingest_exec_done()
