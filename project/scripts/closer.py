#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FSM CLOSE — gest -> closer -> exec

Règles :
- gest.status = close_req | partial_req
- closer crée close_stdby
- exec exécute
"""

import sqlite3
import time
import logging
from pathlib import Path

ROOT = Path("/opt/scalp/project")

DB_GEST   = ROOT / "data/gest.db"
DB_CLOSER = ROOT / "data/closer.db"

LOG = ROOT / "logs/closer.log"

logging.basicConfig(
    filename=str(LOG),
    level=logging.INFO,
    format="%(asctime)s CLOSER %(levelname)s %(message)s"
)
log = logging.getLogger("CLOSER")


def conn(db):
    c = sqlite3.connect(str(db), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c


def now_ms():
    return int(time.time() * 1000)


# ==========================================================
# INGESTION gest -> closer
# ==========================================================
def ingest_from_gest():
    g = conn(DB_GEST)
    c = conn(DB_CLOSER)

    try:
        rows = g.execute("""
            SELECT
                uid,
                instId,
                side,
                step,
                status,
                ratio_to_close,
                reason
            FROM gest
            WHERE status IN ('close_req','partial_req')
        """).fetchall()

        for r in rows:
            uid   = r["uid"]
            step  = int(r["step"])
            stat  = r["status"]

            # map status -> exec_type
            if stat == "close_req":
                exec_type = "close"
            elif stat == "partial_req":
                exec_type = "partial"
            else:
                continue

            exists = c.execute("""
                SELECT 1 FROM closer
                WHERE uid=? AND exec_type=? AND step=?
            """, (uid, exec_type, step)).fetchone()

            if exists:
                continue

            c.execute("""
                INSERT INTO closer (
                    uid,
                    instId,
                    side,
                    exec_type,
                    step,
                    ratio_to_close,
                    status,
                    ts_create,
                    reason
                ) VALUES (?, ?, ?, ?, ?, ?, 'close_stdby', ?, ?)
            """, (
                uid,
                r["instId"],
                r["side"],
                exec_type,
                step,
                r["ratio_to_close"],
                now_ms(),
                r["reason"]
            ))

            log.info(
                "[INGEST] close_stdby uid=%s type=%s step=%s",
                uid, exec_type, step
            )

        c.commit()

    except Exception:
        log.exception("[ERR] ingest_from_gest")
        try:
            c.rollback()
        except Exception:
            pass
    finally:
        g.close()
        c.close()


# ==========================================================
# MAIN LOOP
# ==========================================================
def main():
    log.info("[START] closer")

    while True:
        ingest_from_gest()
        time.sleep(0.2)


if __name__ == "__main__":
    main()
