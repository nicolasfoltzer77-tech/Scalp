#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import time
import math
import logging
from pathlib import Path

from opener_sizing import apply_contract_constraints

ROOT = Path("/opt/scalp/project")

DB_GEST      = ROOT / "data/gest.db"
DB_OPENER    = ROOT / "data/opener.db"
DB_CONTRACTS = ROOT / "data/contracts.db"
DB_EXEC      = ROOT / "data/exec.db"

log = logging.getLogger("OPENER")

def _conn(p: Path):
    c = sqlite3.connect(str(p), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c

def now_ms():
    return int(time.time() * 1000)

def _f(x, d=0.0):
    try:
        if x is None:
            return d
        return float(x)
    except Exception:
        return d

def _next_pyramide_step(edb, uid: str) -> int:
    # step pyramide monotone par uid pour éviter collision + permettre plusieurs ajouts
    r = edb.execute("""
        SELECT COALESCE(MAX(step), -1) AS mx
        FROM exec
        WHERE uid=? AND exec_type='pyramide'
    """, (uid,)).fetchone()
    mx = int(r["mx"] if r and r["mx"] is not None else -1)
    return mx + 1

def ingest_pyramide_req():
    g   = _conn(DB_GEST)
    o   = _conn(DB_OPENER)
    cdb = _conn(DB_CONTRACTS)
    edb = _conn(DB_EXEC)

    try:
        rows = g.execute("""
            SELECT uid, instId, side, ratio_to_add
            FROM gest
            WHERE status='pyramide_req'
        """).fetchall()

        if not rows:
            return

        for r in rows:
            uid    = r["uid"]
            instId = r["instId"]
            side   = r["side"]
            ratio  = _f(r["ratio_to_add"], 0.0)

            if not uid or not instId or side not in ("buy", "sell") or ratio <= 0:
                continue

            # position réelle + dernier prix exec (via v_exec_position)
            pos = edb.execute("""
                SELECT qty_open, last_price_exec
                FROM v_exec_position
                WHERE uid=?
                LIMIT 1
            """, (uid,)).fetchone()

            qty_pos = _f(pos["qty_open"], 0.0) if pos else 0.0
            price   = _f(pos["last_price_exec"], 0.0) if pos else 0.0

            if qty_pos <= 0 or price <= 0:
                continue

            # contrat
            sym = instId.replace("/", "")
            contract = cdb.execute("""
                SELECT * FROM contracts WHERE symbol=? LIMIT 1
            """, (sym,)).fetchone()

            if not contract:
                log.info("[PYR_SKIP] uid=%s inst=%s reason=no_contract", uid, instId)
                continue

            min_usdt  = _f(contract["minTradeUSDT"], 0.0)
            min_qty   = _f(contract["minTradeNum"], 0.0)
            step_size = _f(contract["sizeMultiplier"], 1.0)
            if step_size <= 0:
                step_size = 1.0

            # sizing pyramide (ratio)
            qty_raw = qty_pos * ratio

            # --- scale up AU-DESSUS du min notional + step ---
            notional = qty_raw * price
            if min_usdt > 0 and notional < min_usdt:
                qty_min = (min_usdt / price)
                steps = math.ceil(qty_min / step_size)
                qty_raw = steps * step_size

            # respect min_qty (au-dessus)
            if min_qty > 0 and qty_raw < min_qty:
                steps = math.ceil(min_qty / step_size)
                qty_raw = steps * step_size

            qty_norm = apply_contract_constraints(qty_raw, price, contract)
            qty_norm = _f(qty_norm, 0.0)

            if qty_norm <= 0:
                log.info("[PYR_SKIP] uid=%s inst=%s reason=contract_filter qty_raw=%.10f price=%.10f min_usdt=%.4f",
                         uid, instId, _f(qty_raw, 0.0), price, min_usdt)
                continue

            step = _next_pyramide_step(edb, uid)

            # anti-dup opener PK (uid, exec_type, step)
            if o.execute("""
                SELECT 1 FROM opener
                WHERE uid=? AND exec_type='pyramide' AND step=?
                LIMIT 1
            """, (uid, step)).fetchone():
                continue

            ts = now_ms()

            # IMPORTANT: status = 'pyramide_stdby' (sinon exec.py traite comme open)
            o.execute("""
                INSERT OR REPLACE INTO opener
                (uid, instId, side, qty, lev, ts_open, price_exec_open,
                 status, exec_type, step, ratio, qty_raw, qty_norm, reject_reason)
                VALUES (?, ?, ?, ?, 1, ?, ?, 'pyramide_stdby', 'pyramide', ?,
                        ?, ?, ?, NULL)
            """, (uid, instId, side, qty_norm, ts, price, step,
                  ratio, _f(qty_raw, 0.0), qty_norm))

            log.info("[PYR_STDBY] uid=%s inst=%s side=%s step=%d ratio=%.4f qty_pos=%.10f qty=%.10f price=%.10f",
                     uid, instId, side, step, ratio, qty_pos, qty_norm, price)

        o.commit()

    finally:
        g.close()
        o.close()
        cdb.close()
        edb.close()

if __name__ == "__main__":
    ingest_pyramide_req()

