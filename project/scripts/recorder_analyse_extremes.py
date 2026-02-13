#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RECORDER — ANALYSE DES EXTREMES (BEST / WORST TRADE)

- Lecture seule recorder.db
- Reconstruction FSM complète
- Focus MFE / MAE / sorties
"""

import sqlite3
from pathlib import Path

DB = Path("/opt/scalp/project/data/recorder.db")

# ============================================================
# UTILS
# ============================================================

def conn():
    c = sqlite3.connect(str(DB))
    c.row_factory = sqlite3.Row
    return c

def print_block(title):
    print("\n" + title)
    print("=" * len(title))

def fmt(v, n=4):
    return f"{v:+.{n}f}" if v is not None else "NA"

# ============================================================
# LOAD
# ============================================================

with conn() as c:
    trades = c.execute("""
        SELECT
            uid,
            instId,
            side,
            pnl_realized,
            mfe_atr,
            mae_atr,
            nb_partial,
            nb_pyramide,
            reason_close,
            ts_open,
            ts_close,
            type_signal,
            dec_mode
        FROM recorder
    """).fetchall()

if not trades:
    print("Aucun trade.")
    exit(0)

best = max(trades, key=lambda r: r["pnl_realized"])
worst = min(trades, key=lambda r: r["pnl_realized"])

# ============================================================
# CORE PRINT
# ============================================================

def analyse_trade(label, r):
    print_block(f"{label} TRADE — {r['uid']}")

    dur = (
        (r["ts_close"] - r["ts_open"]) / 1000
        if r["ts_open"] and r["ts_close"] else None
    )

    capture = (
        r["pnl_realized"] / r["mfe_atr"]
        if r["mfe_atr"] and r["mfe_atr"] > 0 else None
    )

    print(f"Instrument     : {r['instId']} ({r['side']})")
    print(f"Type / Mode    : {r['type_signal']} / {r['dec_mode']}")
    print(f"PNL            : {fmt(r['pnl_realized'],6)}")
    print(f"Durée          : {dur:.1f}s" if dur else "Durée          : NA")
    print(f"MFE (ATR)      : {fmt(r['mfe_atr'])}")
    print(f"MAE (ATR)      : {fmt(r['mae_atr'])}")
    print(f"Capture        : {fmt(capture)}")
    print(f"Nb partial     : {r['nb_partial']}")
    print(f"Nb pyramide    : {r['nb_pyramide']}")
    print(f"Sortie finale  : {r['reason_close']}")

    # --------------------------------------------------------
    # FSM DETAIL
    # --------------------------------------------------------

    with conn() as c:
        steps = c.execute("""
            SELECT
                step,
                exec_type,
                reason,
                mfe_atr,
                mae_atr,
                golden,
                ts_exec
            FROM recorder_steps
            WHERE uid=?
            ORDER BY ts_exec
        """, (r["uid"],)).fetchall()

    print("\nFSM — DÉROULÉ CHRONOLOGIQUE")
    print("-" * 60)

    for s in steps:
        print(
            f"step={s['step']:>2d} | "
            f"{s['exec_type']:<8s} | "
            f"mfe={fmt(s['mfe_atr'])} | "
            f"mae={fmt(s['mae_atr'])} | "
            f"golden={s['golden']} | "
            f"{s['reason']}"
        )

# ============================================================
# RUN
# ============================================================

analyse_trade("BEST", best)
analyse_trade("WORST", worst)


