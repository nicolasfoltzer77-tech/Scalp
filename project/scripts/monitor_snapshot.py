#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCALP — MONITOR SNAPSHOT (READ ONLY)

- aucune écriture
- aucune attach
- visibilité complète du pipeline
"""

import sqlite3
from pathlib import Path

ROOT = Path("/opt/scalp/project")

DB_UNIVERSE = ROOT / "data/universe.db"
DB_MARKET   = ROOT / "data/market.db"
DB_CTX      = ROOT / "data/a.db"
DB_DEC      = ROOT / "data/dec.db"

# ------------------------------------------------------------
def conn(p):
    c = sqlite3.connect(str(p), timeout=5)
    c.row_factory = sqlite3.Row
    return c

# ------------------------------------------------------------
def universe_snapshot():
    with conn(DB_UNIVERSE) as c:
        r = c.execute("""
            SELECT
              (SELECT COUNT(*) FROM universe_seed)      AS seed,
              (SELECT COUNT(*) FROM v_universe_enabled) AS enabled,
              (SELECT COUNT(*) FROM universe_tradable)  AS tradable
        """).fetchone()
    return r

# ------------------------------------------------------------
def market_snapshot():
    with conn(DB_MARKET) as c:
        r = c.execute("""
            SELECT
              COUNT(*)                                   AS seen,
              SUM(staleness_ms <= 1000)                 AS fresh,
              SUM(ticks_5s >= 5)                        AS flow_ok,
              SUM(spread_bps <= 5.0)                    AS spread_ok,
              SUM(market_ok = 1)                        AS market_ok
            FROM v_market_latest
        """).fetchone()
    return r

# ------------------------------------------------------------
def ctx_snapshot():
    with conn(DB_CTX) as c:
        total = c.execute("SELECT COUNT(*) FROM v_ctx_signal").fetchone()[0]
        ok    = c.execute("SELECT COUNT(*) FROM v_ctx_signal WHERE ctx_ok=1").fetchone()[0]

        by_ctx = {
            r["ctx"]: r["n"]
            for r in c.execute("""
                SELECT ctx, COUNT(*) AS n
                FROM v_ctx_signal
                WHERE ctx_ok=1
                GROUP BY ctx
            """)
        }
    return total, ok, by_ctx

# ------------------------------------------------------------
def ctx_on_market_snapshot():
    with conn(DB_CTX) as c_ctx, conn(DB_MARKET) as c_m:
        market_ok = {
            r["instId"]
            for r in c_m.execute("SELECT instId FROM v_market_latest WHERE market_ok=1")
        }

        rows = c_ctx.execute("""
            SELECT instId, ctx
            FROM v_ctx_signal
            WHERE ctx_ok=1
        """).fetchall()

        total = 0
        by_ctx = {"bullish": 0, "bearish": 0, "flat": 0}

        for r in rows:
            if r["instId"] in market_ok:
                total += 1
                by_ctx[r["ctx"]] += 1

    return total, by_ctx

# ------------------------------------------------------------
def dec_explain_snapshot():
    with conn(DB_DEC) as c:
        base = c.execute("""
            SELECT
              COUNT(*)                                 AS ctx_ok,
              SUM(high_20 IS NOT NULL)                 AS has_range,
              SUM(atr IS NOT NULL)                     AS has_atr,
              SUM(compression_ok = 1)                  AS compression_ok
            FROM v_dec_candidates
        """).fetchone()

        modes = {
            r["dec_mode"]: r["n"]
            for r in c.execute("""
                SELECT dec_mode, COUNT(*) AS n
                FROM v_dec_explain
                GROUP BY dec_mode
            """)
        }

    return base, modes

# ------------------------------------------------------------
def main():
    print("\nPIPELINE SNAPSHOT")
    print("=" * 62)

    # ---------------- UNIVERSE ----------------
    u = universe_snapshot()
    print("\nUNIVERSE")
    print(f"Seed              : {u['seed']}")
    print(f"Enabled (allowed) : {u['enabled']} / {u['seed']}  ({u['enabled']-u['seed']:+d})")
    print(f"Tradable          : {u['tradable']} / {u['enabled']}  ({u['tradable']-u['enabled']:+d})")

    # ---------------- MARKET ----------------
    m = market_snapshot()
    print("\nMARKET FILTERS")
    print(f"Seen by market    : {m['seen']} / {u['tradable']}  ({m['seen']-u['tradable']:+d})")
    print(f"Fresh prices     : {m['fresh']} / {m['seen']}  ({m['fresh']-m['seen']:+d})")
    print(f"Sufficient flow  : {m['flow_ok']} / {m['seen']}  ({m['flow_ok']-m['seen']:+d})")
    print(f"Acceptable spread: {m['spread_ok']} / {m['flow_ok']}  ({m['spread_ok']-m['flow_ok']:+d})")
    print(f"Market OK        : {m['market_ok']} / {m['spread_ok']}  ({m['market_ok']-m['spread_ok']:+d})")

    # ---------------- CTX ----------------
    ctx_total, ctx_ok, by_ctx = ctx_snapshot()
    print("\nCONTEXT (micro)")
    print(f"Directional ctx   : {ctx_ok} / {ctx_total}  ({ctx_ok-ctx_total:+d})")
    for k in ("bullish", "bearish", "flat"):
        print(f"  {k:<14}: {by_ctx.get(k,0)}")

    # ---------------- CTX ∩ MARKET ----------------
    ctx_mkt, by_ctx_mkt = ctx_on_market_snapshot()
    print("\nCTX ON MARKET OK")
    print(f"CTX OK on market  : {ctx_mkt}")
    for k in ("bullish", "bearish", "flat"):
        print(f"  {k:<14}: {by_ctx_mkt.get(k,0)}")

    # ---------------- DEC ----------------
    base, modes = dec_explain_snapshot()
    print("\nDEC (dry-run / explain)")
    print(f"CTX candidates    : {base['ctx_ok']}")
    print(f"  with range      : {base['has_range']} / {base['ctx_ok']}")
    print(f"  with ATR        : {base['has_atr']} / {base['ctx_ok']}")
    print(f"  compression OK  : {base['compression_ok']} / {base['ctx_ok']}")

    for mode in ("PREBREAK","PULLBACK","MOMENTUM","NO_ENTRY"):
        print(f"  {mode:<14}: {modes.get(mode,0)}")

    print("\n" + "=" * 62)

# ------------------------------------------------------------
if __name__ == "__main__":
    main()

