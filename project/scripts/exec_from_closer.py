#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
EXEC ← CLOSER

Le closer fournit directement la quantité à exécuter.
AUCUN ratio n’est lu ici (invariant canon).
"""

import time
import sqlite3
import logging
from pathlib import Path

log = logging.getLogger("EXEC_FROM_CLOSER")

ROOT = Path("/opt/scalp/project")
DB_CLOSER = ROOT / "data/closer.db"
DB_EXEC   = ROOT / "data/exec.db"


def conn(db):
    c = sqlite3.connect(str(db), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA busy_timeout=10000;")
    return c


def ingest_from_closer():
    now = int(time.time() * 1000)

    c = conn(DB_CLOSER)
    e = conn(DB_EXEC)

    try:
        rows = c.execute("""
            SELECT uid, exec_type, step, qty
            FROM closer
            WHERE status='close_req'
        """).fetchall()

        for r in rows:
            uid       = r["uid"]
            exec_type = r["exec_type"]   # close / partial
            step      = int(r["step"])
            qty       = float(r["qty"])

            e.execute("""
                INSERT OR IGNORE INTO exec (
                    exec_id, uid, step,
                    exec_type, side,
                    qty, status, ts_exec
                )
                SELECT
                    hex(randomblob(16)), uid, step,
                    exec_type, side,
                    ?, exec_type || '_stdby', ?
                FROM exec
                WHERE uid=?
                LIMIT 1
            """, (qty, now, uid))

            c.execute("""
                UPDATE closer
                SET status='close_sent',
                    ts_sent=?
                WHERE uid=? AND step=?
            """, (now, uid, step))

            log.info("[INGEST] close uid=%s step=%s qty=%.6f", uid, step, qty)

        e.commit()
        c.commit()

    except Exception:
        log.exception("[ERR] exec_from_closer")
        e.rollback()
        c.rollback()

    finally:
        c.close()
        e.close()


if __name__ == "__main__":
    ingest_from_closer()
