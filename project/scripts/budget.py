#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCALP — BUDGET AGGREGATOR (CANON)

RÔLE STRICT :
- SEUL writer de budget.db
- lit exec.db + recorder.db + balance
- matérialise l'état du capital
- AUCUN ATTACH
- AUCUNE vue inter-DB
- SQLITE SAFE

BOUCLE ~1 Hz
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

DB_EXEC    = ROOT / "data/exec.db"
DB_REC     = ROOT / "data/recorder.db"
DB_BUDGET  = ROOT / "data/budget.db"

LOG = ROOT / "logs/budget.log"
LOOP_SLEEP = 1.0

# ============================================================
# LOG
# ============================================================

logging.basicConfig(
    filename=str(LOG),
    level=logging.INFO,
    format="%(asctime)s BUDGET %(levelname)s %(message)s"
)
log = logging.getLogger("BUDGET")

# ============================================================
# UTILS
# ============================================================

def now_ms():
    return int(time.time() * 1000)

def conn(p, ro=False):
    uri = f"file:{p}?mode=ro" if ro else str(p)
    c = sqlite3.connect(uri, uri=ro, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c

# ============================================================
# INIT SCHEMA
# ============================================================

def init_budget_db():
    b = conn(DB_BUDGET)
    b.executescript("""
    CREATE TABLE IF NOT EXISTS budget_state (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        equity REAL NOT NULL,
        margin_used REAL NOT NULL,
        free_balance REAL NOT NULL,
        risk_ratio REAL NOT NULL,
        pnl_realized REAL NOT NULL,
        fee_total REAL NOT NULL,
        ts_update INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS budget_exposure (
        uid TEXT PRIMARY KEY,
        notional_engaged REAL NOT NULL,
        ts_update INTEGER NOT NULL
    );
    """)
    b.commit()
    b.close()

# ============================================================
# CORE
# ============================================================

def recompute_budget():
    ts = now_ms()

    e = conn(DB_EXEC, ro=True)
    r = conn(DB_REC,  ro=True)
    b = conn(DB_BUDGET)

    # --------------------------------------------------------
    # BALANCE INITIALE
    # --------------------------------------------------------
    row = b.execute("SELECT balance_usdt FROM balance WHERE id=1").fetchone()
    if not row:
        raise RuntimeError("balance_usdt manquant dans budget.db")

    balance_init = float(row["balance_usdt"])

    # --------------------------------------------------------
    # PNL RÉALISÉ (RECORDER)
    # --------------------------------------------------------
    row = r.execute("""
        SELECT COALESCE(SUM(pnl_realized), 0.0) AS pnl
        FROM recorder
    """).fetchone()

    pnl_realized = float(row["pnl"])

    # --------------------------------------------------------
    # FEES TOTALES (EXEC)
    # --------------------------------------------------------
    row = e.execute("""
        SELECT COALESCE(SUM(fee), 0.0) AS fee
        FROM exec
    """).fetchone()

    fee_total = float(row["fee"])

    # --------------------------------------------------------
    # EXPOSITION PAR UID (EXEC)
    # --------------------------------------------------------
    exposures = {}
    for row in e.execute("""
        SELECT uid,
               SUM(ABS(qty * price_exec)) AS notional
        FROM exec
        WHERE exec_type IN ('open','pyramide')
        GROUP BY uid
    """):
        exposures[row["uid"]] = float(row["notional"] or 0.0)

    # --------------------------------------------------------
    # MARGIN UTILISÉE
    # --------------------------------------------------------
    margin_used = sum(exposures.values())

    # --------------------------------------------------------
    # EQUITY / FREE / RISK
    # --------------------------------------------------------
    equity = balance_init + pnl_realized - fee_total
    free_balance = equity - margin_used
    risk_ratio = (margin_used / equity) if equity > 0 else 0.0

    # --------------------------------------------------------
    # WRITE budget_exposure
    # --------------------------------------------------------
    b.execute("DELETE FROM budget_exposure")
    for uid, notion in exposures.items():
        b.execute("""
            INSERT INTO budget_exposure(uid, notional_engaged, ts_update)
            VALUES (?,?,?)
        """, (uid, notion, ts))

    # --------------------------------------------------------
    # WRITE budget_state (UPSERT)
    # --------------------------------------------------------
    b.execute("""
        INSERT INTO budget_state(
            id, equity, margin_used, free_balance,
            risk_ratio, pnl_realized, fee_total, ts_update
        ) VALUES (1,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
            equity=excluded.equity,
            margin_used=excluded.margin_used,
            free_balance=excluded.free_balance,
            risk_ratio=excluded.risk_ratio,
            pnl_realized=excluded.pnl_realized,
            fee_total=excluded.fee_total,
            ts_update=excluded.ts_update
    """, (
        equity, margin_used, free_balance,
        risk_ratio, pnl_realized, fee_total, ts
    ))

    b.commit()
    e.close(); r.close(); b.close()

    log.info(
        "equity=%.2f free=%.2f margin=%.2f risk=%.2f",
        equity, free_balance, margin_used, risk_ratio
    )

# ============================================================
# MAIN
# ============================================================

def main():
    log.info("[START] budget aggregator")
    init_budget_db()

    while True:
        try:
            recompute_budget()
        except Exception:
            log.error("[ERR]\n%s", traceback.format_exc())
        time.sleep(LOOP_SLEEP)

if __name__ == "__main__":
    main()

