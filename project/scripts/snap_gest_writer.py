#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SNAPSHOT GEST → MFE/MAE DB
# single-writer, read-only pour les autres

import sqlite3
import time
from pathlib import Path

ROOT = Path("/opt/scalp/project")
DB_GEST = ROOT / "data/gest.db"
DB_MFE  = ROOT / "data/mfe_mae.db"

SLEEP = 0.5

def conn(p):
    c = sqlite3.connect(str(p))
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    return c

def main():
    while True:
        g = conn(DB_GEST)
        m = conn(DB_MFE)

        rows = g.execute("""
            SELECT
                uid,
                instId,
                side,
                entry,
                qty,
                atr_signal AS atr,
                status,
                close_step,
                ts_updated
            FROM gest
            WHERE status NOT IN ('close_done','expired')
        """).fetchall()

        for r in rows:
            m.execute("""
                INSERT INTO snap_gest (
                    uid, instId, side,
                    entry, qty, atr,
                    status, close_step, ts_updated
                ) VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(uid) DO UPDATE SET
                    instId=excluded.instId,
                    side=excluded.side,
                    entry=excluded.entry,
                    qty=excluded.qty,
                    atr=excluded.atr,
                    status=excluded.status,
                    close_step=excluded.close_step,
                    ts_updated=excluded.ts_updated
            """, (
                r["uid"], r["instId"], r["side"],
                r["entry"], r["qty"], r["atr"],
                r["status"], r["close_step"],
                r["ts_updated"]
            ))

        m.commit()
        g.close()
        m.close()
        time.sleep(SLEEP)

if __name__ == "__main__":
    main()

