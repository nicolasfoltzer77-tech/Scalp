#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SCALP — MFE / MAE ENGINE (FINAL / STRICT)

RÔLE :
- lit gest.db (read-only)
- lit ticks_hist (read-only)
- écrit UNIQUEMENT mfe_mae.db
- calcule MFE / MAE par UID
- AUCUNE logique métier
"""

import sqlite3
import time
import logging
from pathlib import Path

###############################################################################
# PATHS
###############################################################################

ROOT = Path("/opt/scalp/project")

DB_GEST = ROOT / "data/gest.db"
DB_TICK = ROOT / "data/t.db"
DB_MFE  = ROOT / "data/mfe_mae.db"

LOG = ROOT / "logs/mfe_mae.log"
LOOP_SLEEP = 0.5

###############################################################################
# LOG
###############################################################################

logging.basicConfig(
    filename=str(LOG),
    level=logging.INFO,
    format="%(asctime)s MFE_MAE %(levelname)s %(message)s"
)
log = logging.getLogger("MFE_MAE")

###############################################################################
# UTILS
###############################################################################

def now_ms():
    return int(time.time() * 1000)

def conn(p):
    c = sqlite3.connect(str(p), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c

###############################################################################
# CORE
###############################################################################

def loop():
    g = conn(DB_GEST)
    t = conn(DB_TICK)
    m = conn(DB_MFE)

    now = now_ms()

    # ============================================================
    # 1) GEST SNAPSHOT (UID actifs)
    # ============================================================
    gest_rows = g.execute("""
        SELECT
            uid,
            instId,
            side,
            entry,
            ts_open,
            atr_signal
        FROM gest
        WHERE status IN ('open_done','follow','partial_done','pyramide_done')
          AND ts_open IS NOT NULL
    """).fetchall()

    gest_map = {r["uid"]: r for r in gest_rows}

    # ============================================================
    # 2) PURGE UID ABSENTS DE GEST
    # ============================================================
    db_uids = {
        r["uid"]
        for r in m.execute("SELECT uid FROM mfe_mae")
    }

    for uid in db_uids - set(gest_map.keys()):
        m.execute("DELETE FROM mfe_mae WHERE uid=?", (uid,))
        log.info("[PURGE] uid=%s", uid)

    # ============================================================
    # 3) INGEST NOUVEAUX UID
    # ============================================================
    for uid, r in gest_map.items():
        if m.execute(
            "SELECT 1 FROM mfe_mae WHERE uid=?",
            (uid,)
        ).fetchone():
            continue

        m.execute("""
            INSERT INTO mfe_mae (
                uid, instId, side,
                entry_price, ts_open,
                mfe, mfe_ts,
                mae, mae_ts,
                last_price, last_ts,
                atr,
                ts_updated
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            uid,
            r["instId"],
            r["side"],
            r["entry"],
            r["ts_open"],
            0.0, r["ts_open"],
            0.0, r["ts_open"],
            r["entry"],
            r["ts_open"],
            r["atr_signal"],
            now
        ))

        log.info("[INGEST] uid=%s inst=%s", uid, r["instId"])

    # ============================================================
    # 4) UPDATE MFE / MAE (ticks_hist, fenêtre correcte)
    # ============================================================
    for r in m.execute("SELECT * FROM mfe_mae"):
        ticks = t.execute("""
            SELECT lastPr, ts_ms
            FROM ticks_hist
            WHERE instId=?
              AND ts_ms>=?
            ORDER BY ts_ms
        """, (r["instId"], r["ts_open"])).fetchall()

        if not ticks:
            continue

        mfe = r["mfe"]
        mae = r["mae"]
        mfe_ts = r["mfe_ts"]
        mae_ts = r["mae_ts"]

        for tk in ticks:
            move = (
                tk["lastPr"] - r["entry_price"]
                if r["side"] == "buy"
                else r["entry_price"] - tk["lastPr"]
            )

            if move > mfe:
                mfe = move
                mfe_ts = tk["ts_ms"]

            if move < mae:
                mae = move
                mae_ts = tk["ts_ms"]

        last_price = ticks[-1]["lastPr"]
        last_ts    = ticks[-1]["ts_ms"]

        m.execute("""
            UPDATE mfe_mae
            SET
                mfe=?,
                mfe_ts=?,
                mae=?,
                mae_ts=?,
                last_price=?,
                last_ts=?,
                ts_updated=?
            WHERE uid=?
        """, (
            mfe,
            mfe_ts,
            mae,
            mae_ts,
            last_price,
            last_ts,
            now,
            r["uid"]
        ))

    m.commit()
    g.close()
    t.close()
    m.close()

###############################################################################
# MAIN
###############################################################################

def main():
    log.info("[START] mfe_mae engine running (FINAL)")
    while True:
        try:
            loop()
        except Exception:
            log.exception("[ERR] mfe_mae loop")
        time.sleep(LOOP_SLEEP)

if __name__ == "__main__":
    main()

