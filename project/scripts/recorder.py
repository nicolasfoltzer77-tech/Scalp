#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCALP — RECORDER (FINAL / SCHEMA-SAFE + STEPS)

RÈGLES :
- SEUL writer de recorder.db
- AUCUN calcul métier
- AUCUNE logique décisionnelle
- gest = snapshot FSM final
- exec = source de vérité (ledger)
- recorder = 1 ligne / trade
- recorder_steps = N lignes / trade (1 par step exec)
"""

import sqlite3
import time
import logging
import traceback
from pathlib import Path

# ============================================================
# PATHS
# ============================================================

ROOT = Path("/opt/scalp/project")

DB_GEST = ROOT / "data/gest.db"
DB_EXEC = ROOT / "data/exec.db"
DB_REC  = ROOT / "data/recorder.db"

LOG = ROOT / "logs/recorder.log"
SLEEP = 0.5

logging.basicConfig(
    filename=str(LOG),
    level=logging.INFO,
    format="%(asctime)s RECORDER %(levelname)s %(message)s"
)
log = logging.getLogger("RECORDER")

# ============================================================
# UTILS
# ============================================================

def now_ms():
    return int(time.time() * 1000)

def conn(db):
    c = sqlite3.connect(str(db), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c

def rget(row, key, default=None):
    try:
        return row[key]
    except Exception:
        return default

def table_columns(c, table_name):
    return [r["name"] for r in c.execute(f"PRAGMA table_info({table_name})")]

# ============================================================
# INIT recorder_steps (IDEMPOTENT)
# ============================================================

def ensure_recorder_steps():
    c = conn(DB_REC)
    c.execute("""
        CREATE TABLE IF NOT EXISTS recorder_steps (
            uid        TEXT NOT NULL,
            step       INTEGER NOT NULL,

            exec_type  TEXT,
            reason     TEXT,

            price_exec REAL,
            qty_exec   REAL,
            ts_exec    INTEGER,

            sl_be      REAL,
            sl_trail   REAL,
            tp_dyn     REAL,

            mfe_atr    REAL,
            mae_atr    REAL,
            golden     INTEGER,

            PRIMARY KEY (uid, step)
        );
    """)
    c.commit()
    c.close()

# ============================================================
# LOAD PNL (SOURCE DE VÉRITÉ)
# ============================================================

def load_pnl(uid):
    c = conn(DB_EXEC)
    r = c.execute("""
        SELECT pnl_realized
        FROM v_exec_pnl_uid
        WHERE uid=?
    """, (uid,)).fetchone()
    c.close()
    return float(r["pnl_realized"]) if r and r["pnl_realized"] is not None else 0.0

# ============================================================
# FETCH FINAL TRADES FROM GEST
# ============================================================

def fetch_close_done():
    c = conn(DB_GEST)
    rows = c.execute("""
        SELECT *
        FROM gest
        WHERE status='close_done'
    """).fetchall()
    c.close()
    return rows

# ============================================================
# VALUE MAPPING (GEST -> RECORDER)
# ============================================================

def build_value_for_column(col, g, pnl_realized, ts_rec):
    if col in ("pnl_realized", "pnl", "pnl_net"):
        return pnl_realized
    if col == "ts_recorded":
        return ts_rec
    if col == "close_steps":
        return rget(g, "close_steps", rget(g, "close_step"))
    if col == "price_exec_close":
        return rget(g, "price_exec_close", rget(g, "avg_exit_price"))
    return rget(g, col)

def normalize_required(col, v):
    if col in ("price_signal",) and v is None:
        return 0.0
    return v

# ============================================================
# RECORD STEPS (EXEC -> recorder_steps)
# ============================================================

def record_steps(uid):
    e = conn(DB_EXEC)
    r = conn(DB_REC)

    rows = e.execute("""
        SELECT
            uid,
            step,
            exec_type,
            reason,
            price_exec,
            qty,
            ts_exec,
            sl_be,
            sl_trail,
            tp_dyn,
            mfe_atr,
            mae_atr,
            golden
        FROM exec
        WHERE uid=?
        ORDER BY step
    """, (uid,)).fetchall()

    for x in rows:
        r.execute("""
            INSERT OR IGNORE INTO recorder_steps (
                uid, step,
                exec_type, reason,
                price_exec, qty_exec, ts_exec,
                sl_be, sl_trail, tp_dyn,
                mfe_atr, mae_atr, golden
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            x["uid"],
            x["step"],
            x["exec_type"],
            x["reason"],
            x["price_exec"],
            x["qty"],
            x["ts_exec"],
            x["sl_be"],
            x["sl_trail"],
            x["tp_dyn"],
            x["mfe_atr"],
            x["mae_atr"],
            x["golden"]
        ))

    r.commit()
    e.close()
    r.close()

# ============================================================
# RECORD TRADE (GEST -> recorder)
# ============================================================

def record_trade(g):
    uid = rget(g, "uid")
    if not uid:
        return

    c = conn(DB_REC)
    if c.execute("SELECT 1 FROM recorder WHERE uid=?", (uid,)).fetchone():
        c.close()
        return

    rec_cols = table_columns(c, "recorder")
    c.close()

    pnl_realized = load_pnl(uid)
    ts_rec = now_ms()

    values = []
    for col in rec_cols:
        v = build_value_for_column(col, g, pnl_realized, ts_rec)
        v = normalize_required(col, v)
        values.append(v)

    placeholders = ",".join(["?"] * len(rec_cols))
    col_list = ",".join(rec_cols)

    c = conn(DB_REC)
    c.execute(f"INSERT INTO recorder ({col_list}) VALUES ({placeholders})", values)
    c.commit()
    c.close()

    record_steps(uid)

    log.info("[RECORDED] %s pnl=%+.6f (steps copied)", uid, pnl_realized)

# ============================================================
# MAIN
# ============================================================

def main():
    log.info("[START] recorder FINAL (with steps)")
    ensure_recorder_steps()

    while True:
        try:
            for g in fetch_close_done():
                record_trade(g)
        except Exception:
            log.error("[ERR]\n%s", traceback.format_exc())
        time.sleep(SLEEP)

if __name__ == "__main__":
    main()

