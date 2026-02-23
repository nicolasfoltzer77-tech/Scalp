#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
EXEC <- CLOSER
Ingestion des ordres de fermeture depuis closer *_stdby.
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
            SELECT uid, instId, side, exec_type, step, qty, reason
            FROM closer
            WHERE status IN ('partial_stdby','close_stdby')
        """).fetchall()

        for r in rows:
            uid = r["uid"]
            exec_type = r["exec_type"]
            step = int(r["step"] or 0)
            qty = float(r["qty"] or 0.0)
            exec_id = f"{uid}:{exec_type}:{step}"

            if qty <= 0:
                continue

            exists = e.execute("SELECT 1 FROM exec WHERE exec_id=?", (exec_id,)).fetchone()
            if exists:
                continue

            e.execute("""
                INSERT INTO exec (
                    exec_id, uid, step,
                    exec_type, side,
                    qty, price_exec, fee,
                    status, ts_exec, reason, instId, lev
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                exec_id,
                uid,
                step,
                exec_type,
                r["side"],
                qty,
                0.0,
                0.0,
                "open",
                now,
                r["reason"],
                r["instId"],
                1.0,
            ))

            log.info("[INGEST] uid=%s type=%s step=%s qty=%.6f", uid, exec_type, step, qty)

        e.commit()

    except Exception:
        log.exception("[ERR] exec_from_closer")
        e.rollback()

    finally:
        c.close()
        e.close()


if __name__ == "__main__":
    ingest_from_closer()
