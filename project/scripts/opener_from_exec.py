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
    o = conn(DB_OPENER)
    e = conn(DB_EXEC)

    try:
        rows = o.execute("""
            SELECT *
            FROM opener
            WHERE status='open_stdby'
              AND exec_type='open'
        """).fetchall()

        for r in rows:
            uid   = r["uid"]
            inst  = r["instId"]
            side  = r["side"]
            qty   = float(r["qty"] or 0.0)
            step  = int(r["step"] or 0)

            exec_id = f"{uid}_open_{step}"

            # déjà exécuté ?
            if e.execute("SELECT 1 FROM exec WHERE exec_id=?", (exec_id,)).fetchone():
                continue

            # ⬇️ SCHEMA EXEC RÉEL COMPATIBLE (AUCUN BREAK)
            e.execute("""
                INSERT INTO exec (
                    exec_id, uid, step, exec_type, side,
                    qty, price_exec, fee,
                    status, ts_exec,
                    ts_ack, ts_done,
                    instId, ratio,
                    pnl, pnl_pct,
                    slippage, latency,
                    flags, comment,
                    retry, err_code,
                    reserved1, reserved2
                )
                VALUES (?,?,?,?,?,
                        ?,?,?,
                        'done',?,
                        NULL,NULL,
                        ?,1.0,
                        0.0,0.0,
                        0.0,0.0,
                        0,'',
                        0,0,
                        0,0)
            """, (
                exec_id, uid, step, 'open', side,
                qty, 0.0, 0.0,
                now_ms(),
                inst
            ))

            o.execute("""
                UPDATE opener
                SET status='open_done',
                    price_exec_open=0.0
                WHERE uid=? AND step=? AND exec_type='open'
            """, (uid, step))

            log.info("[EXEC_OPEN] uid=%s step=%d qty=%f", uid, step, qty)

        e.commit()
        o.commit()

    finally:
        o.close()
        e.close()

