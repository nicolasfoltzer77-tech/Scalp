#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import time
from pathlib import Path
import logging

log = logging.getLogger("EXEC_FROM_OPENER")

ROOT = Path("/opt/scalp/project")
DB_OPENER = ROOT / "data/opener.db"
DB_EXEC   = ROOT / "data/exec.db"


def conn(db):
    c = sqlite3.connect(str(db), timeout=5)
    c.row_factory = sqlite3.Row
    return c


def now_ms():
    return int(time.time() * 1000)


def ingest_from_opener():
    o = conn(DB_OPENER)
    e = conn(DB_EXEC)

    try:
        rows = o.execute("""
            SELECT uid, instId, side, qty, lev, exec_type, step
            FROM opener
            WHERE status IN ('open_stdby', 'pyramide_stdby')
        """).fetchall()

        for r in rows:
            exec_id = f"{r['uid']}:{r['exec_type']}:{r['step']}"

            exists = e.execute(
                "SELECT 1 FROM exec WHERE exec_id=?",
                (exec_id,)
            ).fetchone()

            if exists:
                log.debug(
                    "[SKIP] already ingested uid=%s step=%s",
                    r["uid"], r["step"]
                )
                continue

            e.execute("""
                INSERT INTO exec (
                    exec_id, uid, step, exec_type, side,
                    qty, price_exec, fee, status,
                    ts_exec, instId, lev
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                exec_id,
                r["uid"],
                int(r["step"]),
                r["exec_type"],
                r["side"],
                r["qty"],
                0.0,
                0.0,
                "open",
                now_ms(),
                r["instId"],
                r["lev"],
            ))

            log.info(
                "[INGEST] uid=%s inst=%s type=%s side=%s qty=%s step=%s",
                r["uid"],
                r["instId"],
                r["exec_type"],
                r["side"],
                r["qty"],
                r["step"]
            )

        e.commit()

    except Exception:
        log.exception("[ERR] exec_from_opener")
        try:
            e.rollback()
        except Exception:
            pass
    finally:
        o.close()
        e.close()
