#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GEST FSM SYNC — STEP PROPAGATION

Règle :
- EXEC est l’autorité du step
- OPENER / CLOSER copient step depuis EXEC
- GEST copie step depuis OPENER / CLOSER
- AUCUN calcul ici
"""

import time
import sqlite3
import logging
from pathlib import Path

log = logging.getLogger("GEST_FSM_SYNC")

ROOT = Path("/opt/scalp/project")

DB_GEST   = ROOT / "data/gest.db"
DB_OPENER = ROOT / "data/opener.db"
DB_CLOSER = ROOT / "data/closer.db"


def conn(db):
    c = sqlite3.connect(str(db), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c


def now_ms():
    return int(time.time() * 1000)


def main():
    log.info("[START] gest_fsm_sync")

    g = conn(DB_GEST)
    o = conn(DB_OPENER)
    c = conn(DB_CLOSER)

    try:
        # --------------------------------------------------
        # Sync STEP from OPENER (open / pyramide)
        # --------------------------------------------------
        rows_opener = o.execute("""
            SELECT uid, step
            FROM opener
            WHERE status='open_done'
        """).fetchall()

        for r in rows_opener:
            g.execute("""
                UPDATE gest
                SET step=?,
                    ts_updated=?
                WHERE uid=?
            """, (
                r["step"],
                now_ms(),
                r["uid"]
            ))

        # --------------------------------------------------
        # Sync STEP from CLOSER (partial / close)
        # --------------------------------------------------
        rows_closer = c.execute("""
            SELECT uid, step
            FROM closer
            WHERE status='close_done'
        """).fetchall()

        for r in rows_closer:
            g.execute("""
                UPDATE gest
                SET step=?,
                    ts_updated=?
                WHERE uid=?
            """, (
                r["step"],
                now_ms(),
                r["uid"]
            ))

        g.commit()

    except Exception:
        log.exception("[ERR] gest_fsm_sync")
        try:
            g.rollback()
        except Exception:
            pass

    finally:
        g.close()
        o.close()
        c.close()


if __name__ == "__main__":
    main()
