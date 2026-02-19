#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCALP — OPENER FROM GEST (FIX qty NOT NULL)

- lecture gest.db (read-only)
- ingestion gest.open_req → opener.open_stdby
- correction FSM-safe des champs NOT NULL
- aligné schema/db_schema_20260213_130003.txt
"""

import sqlite3
import time
import logging
from pathlib import Path

log = logging.getLogger("OPENER_FROM_GEST")

ROOT = Path("/opt/scalp/project")

DB_GEST   = ROOT / "data/gest.db"
DB_OPENER = ROOT / "data/opener.db"


def conn_gest():
    c = sqlite3.connect(f"file:{DB_GEST}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def conn_opener():
    c = sqlite3.connect(str(DB_OPENER), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c


def now_ms():
    return int(time.time() * 1000)


def ingest_from_gest():
    g = conn_gest()
    o = conn_opener()

    try:
        rows = g.execute("""
            SELECT
                uid,
                instId,
                side,
                qty,
                lev,
                step,
                ts_signal
            FROM gest
            WHERE status='open_req'
        """).fetchall()

        inserted = 0

        for r in rows:
            uid = r["uid"]
            step = r["step"] if r["step"] is not None else 0

            # --------------------------------------------------
            # NORMALISATION FSM (NOT NULL)
            # --------------------------------------------------
            qty = r["qty"]
            if qty is None:
                qty = 0.0
                log.info(
                    "[NORMALIZE] uid=%s qty NULL → 0.0 (open_stdby)",
                    uid
                )

            lev = r["lev"] if r["lev"] is not None else 1.0

            exists = o.execute("""
                SELECT 1
                FROM opener
                WHERE uid=? AND exec_type='open' AND step=?
            """, (uid, step)).fetchone()

            if exists:
                continue

            o.execute("""
                INSERT INTO opener (
                    uid,
                    instId,
                    side,
                    qty,
                    lev,
                    ts_open,
                    price_exec_open,
                    status,
                    exec_type,
                    step
                ) VALUES (?, ?, ?, ?, ?, ?, NULL, 'open_stdby', 'open', ?)
            """, (
                uid,
                r["instId"],
                r["side"],
                qty,
                lev,
                r["ts_signal"],
                step
            ))

            inserted += 1
            log.info(
                "[INGEST_OPEN_REQ] uid=%s instId=%s side=%s qty=%s lev=%s step=%s",
                uid,
                r["instId"],
                r["side"],
                qty,
                lev,
                step
            )

        if inserted > 0:
            o.commit()
            log.info("[INGEST_SUMMARY] inserted=%s", inserted)
        else:
            o.rollback()

    except Exception:
        log.exception("[ERR] opener_from_gest")
        try:
            o.rollback()
        except Exception:
            pass

    finally:
        g.close()
        o.close()
