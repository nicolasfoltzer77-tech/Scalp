#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import time
import logging
from pathlib import Path

from opener_sizing import compute_ticket_qty, apply_contract_constraints

ROOT = Path("/opt/scalp/project")

DB_GEST      = ROOT / "data/gest.db"
DB_OPENER    = ROOT / "data/opener.db"
DB_CONTRACTS = ROOT / "data/contracts.db"
DB_BUDGET    = ROOT / "data/budget.db"

log = logging.getLogger("OPENER")


def conn(db):
    c = sqlite3.connect(str(db), timeout=10)
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


def _get_budget_usdt(b):
    row = b.execute("SELECT balance_usdt FROM balance WHERE id=1").fetchone()
    if not row:
        return None
    return _f(row["balance_usdt"], None)


def _get_contract(k, instId):
    sym = (instId or "").replace("/", "")
    if not sym:
        return None
    return k.execute("SELECT * FROM contracts WHERE symbol=? LIMIT 1", (sym,)).fetchone()


def ingest_open_req():
    g = conn(DB_GEST)
    o = conn(DB_OPENER)
    k = conn(DB_CONTRACTS)
    b = conn(DB_BUDGET)

    try:
        rows = g.execute("""
            SELECT uid, instId, side, price_signal, score_C, score_S, score_H, step
            FROM gest
            WHERE status='open_req'
        """).fetchall()

        if not rows:
            return

        budget_usdt = _get_budget_usdt(b)
        if budget_usdt is None:
            log.error("[OPEN] budget.db missing row id=1 (balance.balance_usdt)")
            return

        market_risk = 1.0

        for r in rows:
            uid    = r["uid"]
            instId = r["instId"]
            side   = r["side"]
            step   = int(r["step"] or 0)

            price   = _f(r["price_signal"], 0.0)
            score_C = _f(r["score_C"], 0.0)
            score_S = _f(r["score_S"], 0.0)
            score_H = _f(r["score_H"], 0.0)

            if not instId or side not in ("buy", "sell") or price <= 0:
                continue

            contract = _get_contract(k, instId)
            if not contract:
                g.execute("""
                    UPDATE gest
                    SET skipped_reason='no_contract',
                        ts_status_update=?
                    WHERE uid=? AND status='open_req'
                """, (now_ms(), uid))
                log.info("[OPEN_SKIP] uid=%s inst=%s reason=no_contract", uid, instId)
                continue

            qty_ticket, lev, _ = compute_ticket_qty(
                balance_usdt=budget_usdt,
                price=price,
                score_C=score_C,
                score_S=score_S,
                score_H=score_H,
                market_risk=market_risk,
                ticket_ratio=1.0
            )

            # ================================
            # FLOOR MIN NOTIONAL (USDT)
            # ================================
            min_usdt = _f(contract["minTradeUSDT"], 0.0)
            if min_usdt > 0:
                floor_qty_usdt = min_usdt / price
                if qty_ticket < floor_qty_usdt:
                    qty_ticket = floor_qty_usdt

            # ================================
            # FLOOR MIN QTY COIN (CRITICAL FIX)
            # ================================
            min_qty = _f(contract["minTradeNum"], 0.0)
            if min_qty > 0 and qty_ticket < min_qty:
                qty_ticket = min_qty

            qty_norm = apply_contract_constraints(qty_ticket, price, contract)
            qty_norm = _f(qty_norm, 0.0)

            if qty_norm <= 0:
                g.execute("""
                    UPDATE gest
                    SET skipped_reason='min_trade_filter',
                        ts_status_update=?
                    WHERE uid=? AND status='open_req'
                """, (now_ms(), uid))
                log.info("[OPEN_SKIP] uid=%s inst=%s qty_ticket=%.10f price=%.10f",
                         uid, instId, _f(qty_ticket, 0.0), price)
                continue

            if o.execute("""
                SELECT 1 FROM opener
                WHERE uid=? AND exec_type='open' AND step=?
                LIMIT 1
            """, (uid, step)).fetchone():
                continue

            ts_open = now_ms()
            ratio = 1.0

            o.execute("""
                INSERT INTO opener
                (uid, instId, side, qty, lev,
                 ts_open, price_exec_open, status,
                 exec_type, step, ratio, qty_raw, qty_norm, reject_reason)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                uid, instId, side, qty_norm, float(lev),
                ts_open, None, "open_stdby",
                "open", step, ratio, _f(qty_ticket, 0.0), qty_norm, None
            ))

            g.execute("""
                UPDATE gest
                SET qty=?,
                    lev=?,
                    entry=?,
                    ts_open=?,
                    ts_status_update=?
                WHERE uid=? AND status='open_req'
            """, (qty_norm, float(lev), price, ts_open, ts_open, uid))

            log.info("[OPEN_STDBY] uid=%s inst=%s side=%s qty=%.10f lev=%s step=%d budget=%.2f",
                     uid, instId, side, qty_norm, lev, step, budget_usdt)

        o.commit()
        g.commit()

    finally:
        g.close()
        o.close()
        k.close()
        b.close()

