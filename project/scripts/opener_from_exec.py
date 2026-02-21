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
              AND exec_type IN ('open','pyramide')
        """).fetchall()

        for r in rows:
            uid       = r["uid"]
            exec_type = r["exec_type"]
            step_new  = int(r["step"] or 0)
            step_done = step_new - 1

            if step_done < 0:
                continue

            if exec_type == "open":
                status_from = "open_stdby"
                status_to = "open_done"
            else:
                status_from = "pyramide_stdby"
                status_to = "pyramide_done"

            res = o.execute("""
                UPDATE opener
                SET status=?,
                    step=?
                WHERE uid=?
                  AND exec_type=?
                  AND step=?
                  AND status=?
            """, (status_to, step_new, uid, exec_type, step_done, status_from))

            if res.rowcount:
                log.info("[ACK] %s uid=%s step=%s", status_to, uid, step_new)

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
