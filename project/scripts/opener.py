#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import logging
import sqlite3
from pathlib import Path

# ============================================================
# LOGGING
# ============================================================

ROOT = Path("/opt/scalp/project")
LOG  = ROOT / "logs/opener.log"

logging.basicConfig(
    filename=str(LOG),
    level=logging.INFO,
    format="%(asctime)s OPENER %(levelname)s %(message)s"
)

log = logging.getLogger("OPENER")

log.info("========== OPENER BOOT ==========")
log.info("PID=%s", os.getpid())
log.info("__file__=%s", __file__)

# ============================================================
# IMPORTS METIER (SAFE)
# ============================================================

try:
    import opener_from_gest
    import opener_ingest_open
    import opener_pyramide
    import opener_from_exec
    from opener_sizing import compute_ticket_qty
except Exception:
    log.exception("[FATAL] import error")
    raise

# ============================================================
# DB PATHS
# ============================================================

DB_OPENER = ROOT / "data/opener.db"
DB_GEST   = ROOT / "data/gest.db"
DB_BUDGET = ROOT / "data/budget.db"

LOOP_SLEEP = 1.0


def conn_opener():
    c = sqlite3.connect(str(DB_OPENER), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c


def get_balance_usdt():
    c = sqlite3.connect(str(DB_BUDGET))
    try:
        row = c.execute(
            "SELECT balance_usdt FROM balance WHERE id=1"
        ).fetchone()
        return float(row[0]) if row else None
    finally:
        c.close()


def get_price_signal(uid):
    """
    Prix canonique pour le sizing initial.
    """
    c = sqlite3.connect(str(DB_GEST))
    try:
        row = c.execute(
            "SELECT price_signal FROM gest WHERE uid=?",
            (uid,)
        ).fetchone()
        return float(row[0]) if row and row[0] else None
    finally:
        c.close()


# ============================================================
# SIZING (open_stdby -> open_req)
# ============================================================

def run_sizing_opener():
    balance_usdt = get_balance_usdt()
    if not balance_usdt or balance_usdt <= 0:
        log.info("[SIZING_SKIP] invalid balance_usdt=%s", balance_usdt)
        return

    o = conn_opener()

    try:
        rows = o.execute("""
            SELECT
                uid,
                step
            FROM opener
            WHERE status='open_stdby'
              AND exec_type='open'
        """).fetchall()

        for r in rows:
            uid  = r["uid"]
            step = r["step"]

            price = get_price_signal(uid)
            if not price or price <= 0:
                continue

            qty, lev, score = compute_ticket_qty(
                balance_usdt = balance_usdt,
                price        = price,
                score_C      = 0.5,
                score_S      = 0.5,
                score_H      = 0.5,
                market_risk  = 1.0,
                ticket_ratio = 1.0
            )

            if qty <= 0:
                log.info("[SIZING_SKIP] uid=%s qty=0", uid)
                continue

            o.execute("""
                UPDATE opener
                SET qty=?,
                    lev=?,
                    status='open_req'
                WHERE uid=? AND exec_type='open' AND step=?
            """, (
                qty,
                lev,
                uid,
                step
            ))

            log.info(
                "[SIZED] uid=%s price=%s qty=%s lev=%s balance=%s",
                uid,
                price,
                qty,
                lev,
                balance_usdt
            )

        o.commit()

    except Exception:
        log.exception("[ERR] run_sizing_opener")
        try:
            o.rollback()
        except Exception:
            pass
    finally:
        o.close()


# ============================================================
# MAIN LOOP
# ============================================================

def main():
    while True:
        try:
            opener_from_gest.ingest_from_gest()
        except Exception:
            log.exception("[ERR] ingest_from_gest")

        try:
            run_sizing_opener()
        except Exception:
            log.exception("[ERR] run_sizing_opener")

        try:
            opener_ingest_open.ingest_open_req()
        except Exception:
            log.exception("[ERR] ingest_open_req")

        try:
            opener_pyramide.ingest_pyramide_req()
        except Exception:
            log.exception("[ERR] ingest_pyramide_req")

        try:
            if hasattr(opener_from_exec, "ingest_exec_done"):
                opener_from_exec.ingest_exec_done()
            elif hasattr(opener_from_exec, "ingest_exec_ack"):
                opener_from_exec.ingest_exec_ack()
        except Exception:
            log.exception("[ERR] opener_from_exec")

        log.info("[HEARTBEAT] pid=%s", os.getpid())
        time.sleep(LOOP_SLEEP)


if __name__ == "__main__":
    main()
