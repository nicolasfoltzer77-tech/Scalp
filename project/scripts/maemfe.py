#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCALP — MAE / MFE ENGINE (DEDICATED WRITER)

RÔLE STRICT :
- lit gest.db (trades ouverts)
- lit t.db (ticks)
- calcule MFE / MAE
- écrit UNIQUEMENT dans mfe_mae.db
- aucune décision, aucun blocage
"""

import sqlite3
import time
import logging
from pathlib import Path

# =====================
# PATHS
# =====================
ROOT = Path("/opt/scalp/project")

DB_GEST = ROOT / "data/gest.db"
DB_TICK = ROOT / "data/t.db"
DB_MFE  = ROOT / "data/mfe_mae.db"

LOG = ROOT / "logs/maemfe.log"
LOOP_SLEEP = 0.2

# =====================
# LOG
# =====================
logging.basicConfig(
    filename=str(LOG),
    level=logging.INFO,
    format="%(asctime)s MAEMFE %(levelname)s %(message)s"
)
log = logging.getLogger("MAEMFE")

# =====================
# UTILS
# =====================
def now_ms():
    return int(time.time() * 1000)

def conn(p):
    c = sqlite3.connect(str(p), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c

# =====================
# LOADERS
# =====================
def load_active_trades():
    """
    Trades réellement vivants (post-open)
    """
    with conn(DB_GEST) as c:
        return c.execute("""
            SELECT
                uid,
                instId,
                side,
                avg_entry_price AS entry_price,
                ts_open
            FROM gest
            WHERE status IN (
                'open_done',
                'follow',
                'partial_done'
            )
              AND avg_entry_price IS NOT NULL
        """).fetchall()

def load_ticks():
    with conn(DB_TICK) as c:
        rows = c.execute("""
            SELECT instId_s AS instId, lastPr, ts_ms
            FROM v_ticks_latest
        """).fetchall()
        return {r["instId"]: r for r in rows}

# =====================
# CORE LOOP
# =====================
def process():
    ticks = load_ticks()
    trades = load_active_trades()

    with conn(DB_MFE) as c:
        for t in trades:
            tick = ticks.get(t["instId"])
            if not tick:
                continue

            uid   = t["uid"]
            side  = t["side"]
            entry = t["entry_price"]
            price = tick["lastPr"]
            ts    = tick["ts_ms"]

            move = (entry - price) if side == "sell" else (price - entry)

            row = c.execute(
                "SELECT mfe, mae FROM mfe_mae WHERE uid=?",
                (uid,)
            ).fetchone()

            if row is None:
                # INSERT initial
                mfe = move
                mae = move

                c.execute("""
                    INSERT INTO mfe_mae (
                        uid, instId, side,
                        entry_price, ts_open,
                        mfe, mfe_ts,
                        mae, mae_ts,
                        last_price, last_ts,
                        ts_updated
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    uid,
                    t["instId"],
                    side,
                    entry,
                    t["ts_open"],
                    mfe,
                    ts,
                    mae,
                    ts,
                    price,
                    ts,
                    now_ms()
                ))

                log.info("[INIT] %s mfe=%.5f mae=%.5f", uid, mfe, mae)

            else:
                mfe = max(row["mfe"], move)
                mae = min(row["mae"], move)

                c.execute("""
                    UPDATE mfe_mae
                    SET
                        mfe=?,
                        mfe_ts=CASE WHEN ?>mfe THEN ? ELSE mfe_ts END,
                        mae=?,
                        mae_ts=CASE WHEN ?<mae THEN ? ELSE mae_ts END,
                        last_price=?,
                        last_ts=?,
                        ts_updated=?
                    WHERE uid=?
                """, (
                    mfe,
                    move, ts,
                    mae,
                    move, ts,
                    price,
                    ts,
                    now_ms(),
                    uid
                ))

# =====================
# MAIN
# =====================
def main():
    log.info("[START] maemfe engine running")
    while True:
        try:
            process()
        except Exception as e:
            log.exception("[ERROR] maemfe loop")
        time.sleep(LOOP_SLEEP)

if __name__ == "__main__":
    main()

