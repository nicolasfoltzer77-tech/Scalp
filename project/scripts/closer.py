#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FSM CLOSE — gest -> closer -> exec -> closer_done

Règles :
- gest.status = close_req | partial_req
- closer crée *_stdby (partial_stdby / close_stdby)
- exec exécute puis closer ACK en *_done
"""

import sqlite3
import time
import logging
from pathlib import Path

ROOT = Path("/opt/scalp/project")

DB_GEST   = ROOT / "data/gest.db"
DB_CLOSER = ROOT / "data/closer.db"
DB_EXEC   = ROOT / "data/exec.db"

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


def _table_columns(c, table_name):
    return {r["name"] for r in c.execute(f"PRAGMA table_info({table_name})")}


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

        closer_cols = _table_columns(c, "closer")
        ts_col = "ts_exec" if "ts_exec" in closer_cols else "ts_create"

        for r in rows:
            uid = r["uid"]
            step = int(r["step"] or 0)
            stat = r["status"]

            if stat == "close_req":
                exec_type = "close"
                stdby_status = "close_stdby"
            elif stat == "partial_req":
                exec_type = "partial"
                stdby_status = "partial_stdby"
            else:
                continue

            exists = c.execute(
                "SELECT 1 FROM closer WHERE uid=? AND exec_type=? AND step=?",
                (uid, exec_type, step),
            ).fetchone()
            if exists:
                continue

            c.execute(f"""
                INSERT INTO closer (
                    uid, instId, side, exec_type, step,
                    ratio_to_close, status, {ts_col}, reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                uid,
                r["instId"],
                r["side"],
                exec_type,
                step,
                r["ratio_to_close"],
                stdby_status,
                now_ms(),
                r["reason"],
            ))

            log.info("[INGEST] %s uid=%s type=%s step=%s", stdby_status, uid, exec_type, step)

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
# ACK EXEC -> closer_done
# ==========================================================
def ack_exec_done():
    e = conn(DB_EXEC)
    c = conn(DB_CLOSER)

    try:
        rows = e.execute("""
            SELECT uid, exec_type, step
            FROM exec
            WHERE status='done'
              AND exec_type IN ('partial','close')
        """).fetchall()

        for r in rows:
            uid = r["uid"]
            exec_type = r["exec_type"]
            step_new = int(r["step"] or 0)
            step_done = step_new - 1
            if step_done < 0:
                continue

            if exec_type == "partial":
                status_from, status_to = "partial_stdby", "partial_done"
            else:
                status_from, status_to = "close_stdby", "close_done"

            res = c.execute("""
                UPDATE closer
                SET status=?, step=?, ts_exec=?
                WHERE uid=? AND exec_type=? AND step=? AND status=?
            """, (status_to, step_new, now_ms(), uid, exec_type, step_done, status_from))

            if (res.rowcount or 0) == 0:
                c.execute("""
                    UPDATE closer
                    SET status=?, step=?, ts_exec=?
                    WHERE uid=? AND exec_type=? AND step=? AND status=?
                """, (status_to, step_new, now_ms(), uid, exec_type, step_new, status_from))

        c.commit()

    except Exception:
        log.exception("[ERR] ack_exec_done")
        try:
            c.rollback()
        except Exception:
            pass
    finally:
        e.close()
        c.close()


# ==========================================================
# MAIN LOOP
# ==========================================================
def main():
    log.info("[START] closer")

    while True:
        ingest_from_gest()
        ack_exec_done()
        time.sleep(0.2)


if __name__ == "__main__":
    main()
