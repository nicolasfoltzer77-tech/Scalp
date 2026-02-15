#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
from pathlib import Path
import logging
import time

ROOT = Path("/opt/scalp/project")
DB_OPENER = ROOT / "data/opener.db"
DB_EXEC   = ROOT / "data/exec.db"

log = logging.getLogger("OPENER")


def conn(db):
    c = sqlite3.connect(str(db), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c


def now_ms():
    return int(time.time() * 1000)


def ingest_exec_done():
    """
    exec.db (read-only) -> opener.db (writer)

    Schéma repo (schema/db_schema_20260213_130003.txt) :
      exec(exec_id PK, uid, step, exec_type, side, qty, price_exec, fee, status, ts_exec, instId, lev, ...)
      opener(uid, instId, side, qty, lev, ts_open, price_exec_open, status, exec_type, step, ... PK(uid,exec_type,step))

    Objectif :
      - trouver les opener open_stdby
      - si l'exec open correspondant est done, passer opener -> open_done et copier price_exec_open + ts_open
    """
    o = conn(DB_OPENER)
    e = conn(DB_EXEC)

    try:
        # candidats côté opener
        rows = o.execute("""
            SELECT uid, instId, side, qty, lev, step
            FROM opener
            WHERE status='open_stdby'
              AND exec_type='open'
        """).fetchall()

        for r in rows:
            uid  = r["uid"]
            step = int(r["step"] or 0)

            exec_id = f"{uid}_open_{step}"

            ex = e.execute("""
                SELECT exec_id, uid, step, exec_type, status, price_exec, ts_exec
                FROM exec
                WHERE exec_id=?
                  AND exec_type='open'
                  AND status='done'
            """, (exec_id,)).fetchone()

            if not ex:
                continue

            price_exec = float(ex["price_exec"] or 0.0)
            ts_exec    = int(ex["ts_exec"] or now_ms())

            o.execute("""
                UPDATE opener
                SET status='open_done',
                    price_exec_open=?,
                    ts_open=?
                WHERE uid=?
                  AND exec_type='open'
                  AND step=?
                  AND status='open_stdby'
            """, (price_exec, ts_exec, uid, step))

            log.info("[INGEST_EXEC_DONE] uid=%s step=%d price_exec=%f ts_exec=%d", uid, step, price_exec, ts_exec)

        o.commit()

    finally:
        try:
            o.close()
        finally:
            e.close()
