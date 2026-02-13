#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCALP — CTX MACRO (OB.DB + FEATURES)

RÔLE STRICT :
- Market OK        : market.db / v_market_latest
- Historique prix  : ob.db / ohlcv_5m
- Features         : b.db / v_feat_5m
- Output           : ctx_macro.db (schéma EXISTANT)

MODES :
- --once
- --debug
"""

import sqlite3
import time
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path("/opt/scalp/project")

DB_MARKET = ROOT / "data/market.db"
DB_OB     = ROOT / "data/ob.db"
DB_B      = ROOT / "data/b.db"
DB_CTX    = ROOT / "data/ctx_macro.db"

RET_WINDOW_MS = 15 * 60 * 1000   # 15 minutes
MIN_POINTS = 10

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

# ============================================================
# CORE
# ============================================================

def compute_ctx_macro(debug=False):
    ts = now_ms()

    cM = conn(DB_MARKET)
    cO = conn(DB_OB)
    cB = conn(DB_B)
    cC = conn(DB_CTX)

    # --------------------------------------------------------
    # MARKET OK
    # --------------------------------------------------------
    rows = cM.execute("""
        SELECT instId
        FROM v_market_latest
        WHERE market_ok = 1
    """).fetchall()

    insts = [r["instId"] for r in rows]

    if debug:
        print(f"[DBG] market_ok universe: {len(insts)}")

    reasons = defaultdict(int)
    examples = defaultdict(list)

    returns = []
    atrs = []

    btc_ret = None
    alt_rets = []

    # --------------------------------------------------------
    # PER COIN
    # --------------------------------------------------------
    for inst in insts:
        # latest OHLCV 5m
        r_now = cO.execute("""
            SELECT ts, c
            FROM ohlcv_5m
            WHERE instId=?
            ORDER BY ts DESC
            LIMIT 1
        """, (inst,)).fetchone()

        if not r_now:
            reasons["NO_OHLCV_LATEST"] += 1
            continue

        ts_now = r_now["ts"]
        price_now = r_now["c"]

        # past OHLCV
        r_past = cO.execute("""
            SELECT c
            FROM ohlcv_5m
            WHERE instId=?
              AND ts <= ?
            ORDER BY ts DESC
            LIMIT 1
        """, (inst, ts_now - RET_WINDOW_MS)).fetchone()

        if not r_past:
            reasons["NO_OHLCV_PAST"] += 1
            continue

        price_past = r_past["c"]

        # features 5m (ATR uniquement requis ici)
        f = cB.execute("""
            SELECT atr
            FROM v_feat_5m
            WHERE instId=?
            ORDER BY ts DESC
            LIMIT 1
        """, (inst,)).fetchone()

        if not f or not f["atr"] or f["atr"] <= 0:
            reasons["NO_ATR_FEAT"] += 1
            continue

        ret = (price_now - price_past) / price_past

        returns.append(ret)
        atrs.append(f["atr"])

        if inst.startswith("BTC"):
            btc_ret = ret
        else:
            alt_rets.append(ret)

        if debug and len(examples["PASS"]) < 5:
            examples["PASS"].append(
                f"{inst} ret={ret:+.3%} atr={f['atr']:.6f}"
            )

    # --------------------------------------------------------
    # DEBUG REPORT
    # --------------------------------------------------------
    if debug:
        print(f"[DBG] kept points: {len(returns)}")
        print("[DBG] FAIL REASONS")
        for k, v in reasons.items():
            print(f"  - {k:<18s}: {v}")
        if examples.get("PASS"):
            print("[DBG] PASS SAMPLES")
            for e in examples["PASS"]:
                print("   ", e)

    if len(returns) < MIN_POINTS:
        print(f"[CTX_MACRO] insufficient data (points={len(returns)} < {MIN_POINTS})")
        return

    # --------------------------------------------------------
    # MACRO METRICS
    # --------------------------------------------------------
    breadth = sum(1 for r in returns if abs(r) >= 0.005) / len(returns)

    if breadth >= 0.40:
        breadth_state = "STRONG"
    elif breadth >= 0.20:
        breadth_state = "WEAK"
    else:
        breadth_state = "FLAT"

    direction = statistics.mean(returns)
    if direction > 0:
        direction_state = "BULL"
    elif direction < 0:
        direction_state = "BEAR"
    else:
        direction_state = "MIXED"

    if btc_ret is not None and alt_rets:
        risk_value = statistics.median(alt_rets) - btc_ret
        risk_state = "ON" if risk_value > 0 else "OFF"
    else:
        risk_value = 0.0
        risk_state = "OFF"

    vol_value = statistics.median(atrs)

    hist = cC.execute("""
        SELECT vol_value
        FROM ctx_macro
        ORDER BY ts DESC
        LIMIT 30
    """).fetchall()

    vol_ref = statistics.mean([h["vol_value"] for h in hist]) if hist else vol_value

    if vol_value > vol_ref * 1.3:
        vol_state = "HIGH"
    elif vol_value < vol_ref * 0.7:
        vol_state = "LOW"
    else:
        vol_state = "NORMAL"

    if breadth_state == "STRONG" and direction_state == "BULL":
        regime = "TREND_BULL"
    elif breadth_state == "STRONG" and direction_state == "BEAR":
        regime = "TREND_BEAR"
    elif breadth_state == "FLAT" and vol_state == "LOW":
        regime = "DEAD"
    else:
        regime = "CHOP"

    # --------------------------------------------------------
    # WRITE (ALIGNÉ SCHÉMA ctx_macro)
    # --------------------------------------------------------
    cC.execute("""
        INSERT OR REPLACE INTO ctx_macro (
            ts,
            universe_size,
            breadth_value,
            breadth_state,
            direction_value,
            direction_state,
            risk_value,
            risk_state,
            vol_value,
            vol_state,
            regime
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (
        ts,
        len(insts),
        breadth,
        breadth_state,
        direction,
        direction_state,
        risk_value,
        risk_state,
        vol_value,
        vol_state,
        regime
    ))

    cC.commit()

    print(
        "[CTX_MACRO]",
        f"U={len(insts)}",
        f"points={len(returns)}",
        f"breadth={breadth_state}({breadth:.2f})",
        f"dir={direction_state}",
        f"risk={risk_state}",
        f"vol={vol_state}",
        f"regime={regime}"
    )

    cM.close()
    cO.close()
    cB.close()
    cC.close()

# ============================================================
# MAIN
# ============================================================

def main():
    debug = "--debug" in sys.argv
    once = "--once" in sys.argv

    if once:
        compute_ctx_macro(debug=debug)
        return

    while True:
        compute_ctx_macro(debug=debug)
        time.sleep(60)

if __name__ == "__main__":
    main()

