#!/usr/bin/env python3
import sqlite3
import sys
import time
from datetime import datetime

DB_TRIG   = "data/triggers.db"
DB_TICKS  = "data/t.db"
DB_OB     = "data/ob.db"
DB_CTX    = "data/a.db"
DB_AUDIT  = "data/audit_triggers.db"

WINDOW_MS_DEFAULT = 20000

# -----------------------------------------------------------------------------
def connect(path):
    return sqlite3.connect(path, timeout=30)

# -----------------------------------------------------------------------------
def load_ctx():
    """
    v_ctx_latest:
      instId | ctx | score_C | ts_updated
    """
    c = connect(DB_CTX)
    rows = c.execute("""
        SELECT instId, ctx, score_C
        FROM v_ctx_latest
    """).fetchall()
    c.close()
    return {r[0]: (r[1], r[2]) for r in rows}

# -----------------------------------------------------------------------------
def compute_mfe_mae_from_ticks(inst, side, price_entry, ts0, window_ms):
    c = connect(DB_TICKS)
    rows = c.execute("""
        SELECT lastPr
        FROM ticks_hist
        WHERE instId = ?
          AND ts_ms BETWEEN ? AND ?
    """, (inst.replace('/',''), ts0, ts0 + window_ms)).fetchall()
    c.close()

    if not rows:
        return None, None

    prices = [r[0] for r in rows]

    if side == "buy":
        mfe = max(prices) - price_entry
        mae = min(prices) - price_entry
    else:
        mfe = price_entry - min(prices)
        mae = price_entry - max(prices)

    return mfe, mae

# -----------------------------------------------------------------------------
def compute_mfe_mae_from_ohlcv(inst, side, price_entry, ts0, window_ms):
    c = connect(DB_OB)
    rows = c.execute("""
        SELECT h, l
        FROM ohlcv_1m
        WHERE instId = ?
          AND ts BETWEEN ? AND ?
    """, (inst, ts0, ts0 + window_ms)).fetchall()
    c.close()

    if not rows:
        return 0.0, 0.0

    highs = [r[0] for r in rows]
    lows  = [r[1] for r in rows]

    if side == "buy":
        mfe = max(highs) - price_entry
        mae = min(lows)  - price_entry
    else:
        mfe = price_entry - min(lows)
        mae = price_entry - max(highs)

    return mfe, mae

# -----------------------------------------------------------------------------
def outcome_from_mfe_mae(mfe, mae):
    if mfe > 0 and abs(mfe) > abs(mae):
        return "WIN"
    if mae < 0 and abs(mae) > abs(mfe):
        return "LOSS"
    return "FLAT"

# -----------------------------------------------------------------------------
def audit(reset=False):
    ca = connect(DB_AUDIT)
    ct = connect(DB_TRIG)

    if reset:
        ca.execute("DELETE FROM audit_triggers")
        ca.commit()

    ctx_map = load_ctx()

    rows = ct.execute("""
        SELECT
          uid,
          instId,
          side,
          status,
          price,
          atr,
          ts,
          ts_fire,
          ttl_ms,
          validated
        FROM triggers
        WHERE status = 'fire'
    """).fetchall()

    inserted = 0

    for r in rows:
        uid, inst, side, status, price, atr, ts, ts_fire, ttl_ms, validated = r
        if not ts_fire:
            continue

        window_ms = ttl_ms or WINDOW_MS_DEFAULT
        life_ms   = window_ms

        mfe, mae = compute_mfe_mae_from_ticks(inst, side, price, ts_fire, window_ms)

        if mfe is None:
            mfe, mae = compute_mfe_mae_from_ohlcv(inst, side, price, ts_fire, window_ms)

        outcome = outcome_from_mfe_mae(mfe, mae)

        ctx, score_ctx = ctx_map.get(inst, (None, None))

        ca.execute("""
            INSERT OR IGNORE INTO audit_triggers (
              uid, instId, side, trigger_status,
              price_entry, atr,
              mfe, mae, outcome,
              entry_price,
              mfe_atr, mae_atr,
              ts_trigger,
              window_ms, validated,
              mfe_early, mae_early,
              ttl_ms, life_ms,
              outcome_early,
              ctx, score_ctx
            ) VALUES (
              ?,?,?,?,?,?,
              ?,?,?,?,
              ?,?,
              ?,?,
              ?,?,
              ?,?,
              ?,?,
              ?,?
            )
        """, (
            uid, inst, side, status,
            price, atr or 0.0,
            mfe or 0.0, mae or 0.0, outcome,
            price,
            (mfe/atr) if atr else 0.0,
            (mae/atr) if atr else 0.0,
            ts_fire,
            window_ms, validated or 0,
            mfe or 0.0, mae or 0.0,
            ttl_ms or window_ms,
            life_ms,
            outcome,
            ctx, score_ctx
        ))

        if ca.total_changes > 0:
            inserted += 1

    ca.commit()
    ca.close()
    ct.close()

    print(f"[OK] audit_triggers rows inserted: {inserted}")

# -----------------------------------------------------------------------------
if __name__ == "__main__":
    audit("--reset" in sys.argv)

