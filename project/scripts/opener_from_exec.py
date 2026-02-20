#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FSM ACK — exec -> opener

Règle :
- exec produit step (déjà incrémenté)
- exec.status = 'done'
- opener ACK sur CE step exact
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


def main():
    e = conn(DB_EXEC)
    o = conn(DB_OPENER)

    try:
        rows = e.execute("""
            SELECT uid, exec_type, step
            FROM exec
            WHERE status='done'
        """).fetchall()

        for r in rows:
            uid       = r["uid"]
            exec_type = r["exec_type"]
            step      = int(r["step"])

            if exec_type == "open":
                res = o.execute("""
                    UPDATE opener
                    SET status='open_done'
                    WHERE uid=?
                      AND exec_type='open'
                      AND step=?
                      AND status='open_stdby'
                """, (uid, step))

                if res.rowcount:
                    log.info(
                        "[ACK] open_done uid=%s step=%s",
                        uid, step
                    )

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


if __name__ == "__main__":
    main()
