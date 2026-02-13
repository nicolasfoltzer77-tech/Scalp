#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCALP — GOLDEN TRADE DETECTOR (DESK-GRADE)

Détecte les trades à très forte qualité :
- momentum réel
- drawdown maîtrisé
- scaling (partial + pyramide)
"""

import sqlite3
from pathlib import Path
from statistics import mean

ROOT = Path("/opt/scalp/project")
DB = ROOT / "data/recorder.db"

# ============================================================
# PARAMÈTRES GOLDEN
# ============================================================

CFG = {
    "min_mfe_atr": 2.0,
    "max_mae_atr": 0.5,
    "min_partial": 1,
    "min_pyramide": 1,
}

# ============================================================
# SQLITE
# ============================================================

def conn():
    c = sqlite3.connect(str(DB))
    c.row_factory = sqlite3.Row
    return c

# ============================================================
# LOAD
# ============================================================

with conn() as c:
    rows = c.execute("""
        SELECT
            uid,
            instId,
            pnl,
            mfe_atr,
            mae_atr,
            nb_partial,
            nb_pyramide
        FROM recorder
        WHERE ts_close IS NOT NULL
    """).fetchall()

trades = [dict(r) for r in rows]
if not trades:
    print("Aucun trade.")
    exit(0)

# ============================================================
# GOLDEN FILTER
# ============================================================

def is_golden(t):
    return (
        t["pnl"] is not None and t["pnl"] > 0
        and t["mfe_atr"] is not None and t["mfe_atr"] >= CFG["min_mfe_atr"]
        and t["mae_atr"] is not None and t["mae_atr"] <= CFG["max_mae_atr"]
        and (t["nb_partial"] or 0) >= CFG["min_partial"]
        and (t["nb_pyramide"] or 0) >= CFG["min_pyramide"]
    )

golden = [t for t in trades if is_golden(t)]
non_golden = [t for t in trades if not is_golden(t)]

# ============================================================
# STATS
# ============================================================

def stats(ts):
    if not ts:
        return None
    pnls = [t["pnl"] for t in ts]
    return {
        "n": len(ts),
        "pnl_total": sum(pnls),
        "pnl_mean": mean(pnls),
        "winrate": sum(1 for p in pnls if p > 0) / len(pnls) * 100,
    }

s_all = stats(trades)
s_g   = stats(golden)
s_ng  = stats(non_golden)

# ============================================================
# OUTPUT
# ============================================================

print("\nGOLDEN TRADE DETECTOR")
print("=" * 60)

print("\nRÈGLES")
for k, v in CFG.items():
    print(f"- {k}: {v}")

print("\nRÉPARTITION")
print(f"Total trades : {s_all['n']}")
print(f"Golden       : {s_g['n'] if s_g else 0} ({100*(s_g['n']/s_all['n']):.2f}%)")

print("\nPERFORMANCE")
print("-" * 60)

print("ALL")
print(f"  PNL total : {s_all['pnl_total']:+.4f}")
print(f"  PNL mean  : {s_all['pnl_mean']:+.4f}")
print(f"  Winrate   : {s_all['winrate']:.2f}%")

if s_g:
    print("\nGOLDEN")
    print(f"  PNL total : {s_g['pnl_total']:+.4f}")
    print(f"  PNL mean  : {s_g['pnl_mean']:+.4f}")
    print(f"  Winrate   : {s_g['winrate']:.2f}%")

if s_ng:
    print("\nNON-GOLDEN")
    print(f"  PNL total : {s_ng['pnl_total']:+.4f}")
    print(f"  PNL mean  : {s_ng['pnl_mean']:+.4f}")
    print(f"  Winrate   : {s_ng['winrate']:.2f}%")

# ============================================================
# DÉTAILS
# ============================================================

print("\nLISTE GOLDEN TRADES")
print("=" * 60)
for t in sorted(golden, key=lambda x: x["pnl"], reverse=True):
    print(
        f"{t['instId']:10s} | pnl={t['pnl']:+.4f} | "
        f"mfe_atr={t['mfe_atr']:.2f} | mae_atr={t['mae_atr']:.2f} | "
        f"partial={t['nb_partial']} | pyramide={t['nb_pyramide']}"
    )

