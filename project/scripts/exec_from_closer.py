#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FSM INGEST — closer -> exec

Règle :
- closer.status = close_stdby
- exec ingère UNE FOIS
- exec.status = open
"""

import sqlite3
from pathlib import Path
import logging

log = logging.getLogger("EXEC_FROM_CLOSER")

ROOT = Path("/opt/scalp/project")

DB_CLOSER = ROOT / "data/closer.db"
DB_EXEC   = ROOT / "data/exec.db"


def conn(db):
    c = sqlite3.connect(str(db), timeout=5)
    c.row_factory = sqlite3.Row
    return c


def ingest_from_closer():
    c = conn(DB_CLOSER)
    e = conn(DB_EXEC)

    try:
        rows = c.execute("""
            SELECT
                uid,
                instId,
                side,
                exec_type,
                step,
                ratio_to_close
            FROM closer
            WHERE status='close_stdby'
        """).fetchall()

        for r in rows:
            uid       = r["uid"]
            exec_type = r["exec_type"]          # close | partial
            step      = int(r["step"])

            exec_id = f"{uid}:{exec_type}:{step}"

            exists = e.execute("""
                SELECT 1 FROM exec WHERE exec_id=?
            """, (exec_id,)).fetchone()

            if exists:
                continue

            # qty réelle calculée plus tard via v_exec_position
            e.execute("""
                INSERT INTO exec (
                    exec_id,
                    uid,
                    step,
                    exec_type,
                    side,
                    qty,
                    price_exec,
                    fee,
                    status,
                    ts_exec,
                    instId
                ) VALUES (?, ?, ?, ?, ?, ?, 0.0, 0.0, 'open', ?, ?)
            """, (
                exec_id,
                uid,
                step,
                exec_type,
                r["side"],
                r["ratio_to_close"],   # ratio stocké, exec.py calculera la qty finale
                int(__import__("time").time() * 1000),
                r["instId"]
            ))

            log.info(
                "[INGEST] exec close uid=%s type=%s step=%s",
                uid, exec_type, step
            )

        e.commit()

    except Exception:
        log.exception("[ERR] exec_from_closer")
        try:
            e.rollback()
        except Exception:
            pass
    finally:
        c.close()
        e.close()
