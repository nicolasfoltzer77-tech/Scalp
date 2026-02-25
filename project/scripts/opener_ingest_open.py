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


def _table_columns(conn_, table):
    rows = conn_.execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"] for r in rows}


def _f(x, d=0.0):
    try:
        if x is None:
            return d
        return float(x)
    except Exception:
        return d


def _coalesce_expr(columns, *candidates, default="0.0"):
    present = [c for c in candidates if c in columns]
    if not present:
        return default
    if len(present) == 1:
        return present[0]
    return "COALESCE(" + ", ".join(present + [default]) + ")"


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
        gest_cols = _table_columns(g, "gest")

        # Compat schémas historiques/finals + fallback de valeur:
        # - price_signal puis entry
        # - score_C puis dec_score_C
        # - score_S puis score_of
        # - score_H puis score_force
        # Important: sur schéma final, score_C/score_S/score_H peuvent exister
        # mais rester NULL (ingest écrit dec_score_C/score_of/score_force).
        # On force donc un COALESCE sur colonnes disponibles.
        price_expr = _coalesce_expr(gest_cols, "price_signal", "entry")
        score_c_expr = _coalesce_expr(gest_cols, "score_C", "dec_score_C")
        score_s_expr = _coalesce_expr(gest_cols, "score_S", "score_of")
        score_h_expr = _coalesce_expr(gest_cols, "score_H", "score_force")
        step_expr = "step" if "step" in gest_cols else "0"

        rows = g.execute(f"""
            SELECT uid, instId, side,
                   {price_expr} AS price_signal,
                   {score_c_expr} AS score_C,
                   {score_s_expr} AS score_S,
                   {score_h_expr} AS score_H,
                   {step_expr} AS step
            FROM gest
            WHERE status='open_stdby'
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
                    WHERE uid=? AND status='open_stdby'
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
                    WHERE uid=? AND status='open_stdby'
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

            margin = (qty_norm * price / float(lev)) if float(lev) > 0 else 0.0

            g.execute("""
                UPDATE gest
                SET qty=?,
                    lev=?,
                    margin=?,
                    entry=?,
                    ts_open=?,
                    ts_status_update=?
                WHERE uid=? AND status='open_stdby'
            """, (qty_norm, float(lev), margin, price, ts_open, ts_open, uid))

            log.info("[OPEN_STDBY] uid=%s inst=%s side=%s qty=%.10f lev=%s step=%d budget=%.2f",
                     uid, instId, side, qty_norm, lev, step, budget_usdt)

        o.commit()
        g.commit()

    finally:
        g.close()
        o.close()
        k.close()
        b.close()
