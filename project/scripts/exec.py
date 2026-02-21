#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
EXEC — unique exécuteur FSM

Rôle :
- ingérer opener -> exec (open / pyramide)
- ingérer closer -> exec (close / partial)
- exécuter AU MARCHÉ (ticks)
- écrire price_exec, fee
- passer status -> done
"""

import time
import sqlite3
import logging
from pathlib import Path

from exec_from_opener import ingest_from_opener
from exec_from_closer import ingest_from_closer

# ==================================================
# CONFIG
# ==================================================
ROOT = Path("/opt/scalp/project")

DB_EXEC = ROOT / "data/exec.db"
DB_TICK = ROOT / "data/t.db"

LOG = ROOT / "logs/exec.log"

SPREAD_PCT = 0.0004     # 0.04 %
FEE_PCT    = 0.0006     # 0.06 %
LOOP_SLEEP = 0.2

# ==================================================
# LOGGING
# ==================================================
logging.basicConfig(
    filename=str(LOG),
    level=logging.INFO,
    format="%(asctime)s EXEC %(levelname)s %(message)s"
)
log = logging.getLogger("EXEC")

# ==================================================
# DB helpers
# ==================================================
def conn(db):
    c = sqlite3.connect(str(db), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c


def now_ms():
    return int(time.time() * 1000)

# ==================================================
# MARKET DATA
# ==================================================
def get_last_price(instId):
    t = conn(DB_TICK)
    try:
        row = t.execute("""
            SELECT lastPr
            FROM v_ticks_latest
            WHERE instId=?
            LIMIT 1
        """, (instId,)).fetchone()

        if not row:
            return None

        px = float(row["lastPr"])
        return px if px > 0 else None

    finally:
        t.close()


def apply_spread_and_fee(price, side):
    if side == "buy":
        px = price * (1.0 + SPREAD_PCT)
    else:
        px = price * (1.0 - SPREAD_PCT)

    fee = px * FEE_PCT
    return px, fee

# ==================================================
# MAIN LOOP
# ==================================================
def main():
    log.info("[START] exec")

    while True:

        # 1) ingest FSM
        try:
            ingest_from_opener()
        except Exception:
            log.exception("[ERR] ingest_from_opener")

        try:
            ingest_from_closer()
        except Exception:
            log.exception("[ERR] ingest_from_closer")

        e = conn(DB_EXEC)

        try:
            rows = e.execute("""
                SELECT *
                FROM exec
                WHERE status='open'
            """).fetchall()

            for r in rows:
                uid       = r["uid"]
                exec_id   = r["exec_id"]
                instId    = r["instId"]
                side      = r["side"]
                exec_type = r["exec_type"]
                qty       = float(r["qty"])

                # -------------------------------
                # PRICE DISCOVERY
                # -------------------------------
                last_price = get_last_price(instId)
                if last_price is None:
                    log.warning(
                        "[SKIP] no tick uid=%s inst=%s",
                        uid, instId
                    )
                    continue

                price_exec, fee = apply_spread_and_fee(last_price, side)

                # -------------------------------
                # EXEC DONE  (STEP +1 CANONIQUE)
                # -------------------------------
                e.execute("""
                    UPDATE exec
                    SET status='done',
                        price_exec=?,
                        fee=?,
                        step = step + 1,
                        ts_exec=?,
                        done_step=1
                    WHERE exec_id=?
                """, (
                    price_exec,
                    fee,
                    now_ms(),
                    exec_id
                ))

                log.info(
                    "[EXEC_DONE] uid=%s inst=%s type=%s side=%s qty=%.6f px=%.8f fee=%.8f",
                    uid, instId, exec_type, side, qty, price_exec, fee
                )

            e.commit()

        except Exception:
            log.exception("[ERR] exec loop")
            try:
                e.rollback()
            except Exception:
                pass
        finally:
            e.close()

        time.sleep(LOOP_SLEEP)


if __name__ == "__main__":
    main()
