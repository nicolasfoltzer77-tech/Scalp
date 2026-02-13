#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RECORDER — ANALYSE DE CAPTURE RÉELLE (FSM / STEP AWARE)

But :
- mesurer ce que SL / BE / TRAIL / TP_dyn CAPTURENT réellement
- comparer PNL vs MFE par step
- identifier gestion utile vs cosmétique
"""

import sqlite3
from statistics import mean
from pathlib import Path

DB = Path("/opt/scalp/project/data/recorder.db")

# ============================================================
# UTILS
# ============================================================

def conn():
    c = sqlite3.connect(str(DB))
    c.row_factory = sqlite3.Row
    return c

def avg(xs):
    xs = [x for x in xs if x is not None]
    return mean(xs) if xs else None

def fmt(v, n=4):
    return f"{v:+.{n}f}" if v is not None else "NA"

# ============================================================
# LOAD
# ============================================================

with conn() as c:
    steps = c.execute("""
        SELECT
            uid,
            step,
            exec_type,
            mfe_atr,
            mae_atr,
            reason
        FROM recorder_steps
        WHERE exec_type IN ('partial','close')
        ORDER BY uid, step
    """).fetchall()

    trades = {
        r["uid"]: r
        for r in c.execute("""
            SELECT
                uid,
                pnl_realized,
                mfe_atr,
                mae_atr,
                reason_close
            FROM recorder
        """)
    }

# ============================================================
# ANALYSE
# ============================================================

by_reason = {}
by_step = {}

for s in steps:
    uid = s["uid"]
    r = trades.get(uid)
    if not r:
        continue

    mfe = s["mfe_atr"]
    pnl = r["pnl_realized"]

    capture = pnl / mfe if mfe and mfe > 0 else None

    key_r = s["reason"] or "UNKNOWN"
    key_s = s["step"]

    by_reason.setdefault(key_r, []).append(capture)
    by_step.setdefault(key_s, []).append(capture)

# ============================================================
# OUTPUT
# ============================================================

print("\nCAPTURE RÉELLE PAR TYPE DE SORTIE")
print("=" * 60)

for k, xs in sorted(by_reason.items(), key=lambda x: avg(x[1]) or -999, reverse=True):
    print(
        f"{k:18s} | n={len(xs):3d} "
        f"| cap={fmt(avg(xs))}"
    )

print("\nCAPTURE RÉELLE PAR STEP")
print("=" * 60)

for s in sorted(by_step):
    xs = by_step[s]
    print(
        f"STEP {s:<2d} | n={len(xs):3d} "
        f"| cap={fmt(avg(xs))}"
    )


