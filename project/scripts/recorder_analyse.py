#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RECORDER — ANALYSE GLOBALE AVANCÉE

Inclut :
- performance globale
- admission (step final)
- sorties FSM
- edge par coin
- 🔥 analyse par TYPE D’ENTRÉE (dec_mode / entry_reason / ctx)
- best / worst trades enrichis
"""

import sqlite3
from statistics import mean
from pathlib import Path
from collections import defaultdict

DB = Path("/opt/scalp/project/data/recorder.db")

# ============================================================
# UTILS
# ============================================================

def conn():
    c = sqlite3.connect(str(DB))
    c.row_factory = sqlite3.Row
    return c

def safe(xs):
    return [x for x in xs if x is not None]

def avg(xs):
    xs = safe(xs)
    return mean(xs) if xs else 0.0

def pf(pnls):
    wins = sum(p for p in pnls if p > 0)
    loss = -sum(p for p in pnls if p < 0)
    return wins / loss if loss > 0 else 0.0

def fmt(v, n=4):
    return f"{v:+.{n}f}"

# ============================================================
# LOAD DATA
# ============================================================

with conn() as c:
    rows = c.execute("""
        SELECT
            uid,
            instId,
            side,
            dec_mode,
            entry_reason,
            ctx_close,
            pnl_net,
            pnl,
            fee_total,
            nb_partial,
            nb_pyramide,
            close_steps
        FROM recorder
        WHERE pnl_net IS NOT NULL
    """).fetchall()

trades = []
for r in rows:
    trades.append({
        "uid": r["uid"],
        "inst": r["instId"],
        "side": r["side"],
        "mode": r["dec_mode"] or "UNKNOWN",
        "entry": (r["entry_reason"] or "UNKNOWN").split(":")[0],
        "ctx": r["ctx_close"] or "UNKNOWN",
        "pnl": float(r["pnl"] or 0.0),
        "pnl_net": float(r["pnl_net"] or 0.0),
        "fees": float(r["fee_total"] or 0.0),
        "partial": int(r["nb_partial"] or 0),
        "pyramide": int(r["nb_pyramide"] or 0),
        "step": int(r["close_steps"] or 1),
    })

# ============================================================
# GLOBAL
# ============================================================

print("\nRÉSUMÉ GLOBAL")
print("=" * 70)

pnls = [t["pnl_net"] for t in trades]

print(f"Trades        : {len(trades)}")
print(f"PNL net total : {sum(pnls):+.4f}")
print(f"PNL net moyen : {fmt(avg(pnls))}")
print(f"Profit factor: {pf(pnls):.2f}")

# ============================================================
# RÉPARTITION PAR TYPE D’ENTRÉE
# ============================================================

print("\nRÉPARTITION — TYPE D’ENTRÉE (dec_mode)")
print("=" * 70)

by_mode = defaultdict(list)
for t in trades:
    by_mode[t["mode"]].append(t["pnl_net"])

for mode, xs in sorted(by_mode.items(), key=lambda x: avg(x[1]), reverse=True):
    print(f"{mode:12s} | n={len(xs):3d} | exp={fmt(avg(xs))} | pf={pf(xs):.2f}")

# ============================================================
# TYPE D’ENTRÉE × STEP FINAL
# ============================================================

print("\nTYPE D’ENTRÉE × STEP FINAL")
print("=" * 70)

grid = defaultdict(list)
for t in trades:
    key = (t["mode"], t["step"])
    grid[key].append(t["pnl_net"])

for (mode, step), xs in sorted(grid.items()):
    if len(xs) >= 3:
        print(
            f"{mode:12s} | step={step:<2d} "
            f"| n={len(xs):3d} "
            f"| exp={fmt(avg(xs))} "
            f"| pf={pf(xs):.2f}"
        )

# ============================================================
# EDGE NET — PAR COIN
# ============================================================

print("\nEDGE NET — PAR COIN")
print("=" * 70)

by_inst = defaultdict(list)
for t in trades:
    by_inst[t["inst"]].append(t["pnl_net"])

for inst, xs in sorted(by_inst.items(), key=lambda x: avg(x[1]), reverse=True):
    if len(xs) >= 3:
        print(
            f"{inst:12s} | n={len(xs):3d} "
            f"| exp={fmt(avg(xs))} "
            f"| pf={pf(xs):.2f}"
        )

# ============================================================
# BEST / WORST TRADES
# ============================================================

print("\nBEST 2 TRADES (PNL NET)")
print("=" * 70)

for t in sorted(trades, key=lambda x: x["pnl_net"], reverse=True)[:2]:
    print(
        f"{t['uid']} {t['inst']} {t['side']} "
        f"| net={fmt(t['pnl_net'])} brut={fmt(t['pnl'])} "
        f"fees={fmt(-t['fees'])} "
        f"| step={t['step']} pyr={t['pyramide']} part={t['partial']} "
        f"| entry={t['mode']}"
    )

print("\nWORST 2 TRADES (PNL NET)")
print("=" * 70)

for t in sorted(trades, key=lambda x: x["pnl_net"])[:2]:
    print(
        f"{t['uid']} {t['inst']} {t['side']} "
        f"| net={fmt(t['pnl_net'])} brut={fmt(t['pnl'])} "
        f"fees={fmt(-t['fees'])} "
        f"| step={t['step']} pyr={t['pyramide']} part={t['partial']} "
        f"| entry={t['mode']}"
    )


