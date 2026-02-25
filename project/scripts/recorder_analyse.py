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

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
DB_CANDIDATES = [
    ROOT / "data/recorder.db",
    Path("/opt/scalp/project/data/recorder.db"),
]

# ============================================================
# UTILS
# ============================================================

def pick_db():
    for p in DB_CANDIDATES:
        if p.exists():
            return p
    return DB_CANDIDATES[0]


DB = pick_db()


def conn():
    c = sqlite3.connect(str(DB), timeout=10)
    c.row_factory = sqlite3.Row
    return c


def table_columns(c, table):
    rows = c.execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"] for r in rows}


def first_col(cols, names):
    for n in names:
        if n in cols:
            return n
    return None

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
    cols = table_columns(c, "recorder")

    col_uid = first_col(cols, ["uid"])
    col_inst = first_col(cols, ["instId", "symbol", "inst"])
    col_side = first_col(cols, ["side"])
    col_dec_mode = first_col(cols, ["dec_mode", "trigger_type", "type_signal"])
    col_entry_reason = first_col(cols, ["entry_reason", "reason", "reason_open"])
    col_ctx = first_col(cols, ["ctx_close", "dec_ctx", "ctx"])
    col_pnl_net = first_col(cols, ["pnl_net", "pnl_realized", "pnl"])
    col_pnl = first_col(cols, ["pnl", "pnl_realized", "pnl_net"])
    col_fee = first_col(cols, ["fee_total", "fee", "fee_exec_total"])
    col_partial = first_col(cols, ["nb_partial"])
    col_pyramide = first_col(cols, ["nb_pyramide", "nb_pyramid"])
    col_step = first_col(cols, ["close_steps", "close_step", "last_step", "step"])

    required = {
        "uid": col_uid,
        "inst": col_inst,
        "side": col_side,
        "pnl_net": col_pnl_net,
    }
    missing = [name for name, col in required.items() if col is None]
    if missing:
        raise SystemExit(
            f"Schema recorder incompatible. Colonnes manquantes: {', '.join(missing)}"
        )

    def sel(col, alias, fallback="NULL"):
        if col is None:
            return f"{fallback} AS {alias}"
        return f"{col} AS {alias}"

    sql = f"""
        SELECT
            {sel(col_uid, 'uid')},
            {sel(col_inst, 'instId')},
            {sel(col_side, 'side')},
            {sel(col_dec_mode, 'dec_mode')},
            {sel(col_entry_reason, 'entry_reason')},
            {sel(col_ctx, 'ctx_close')},
            {sel(col_pnl_net, 'pnl_net', '0')},
            {sel(col_pnl, 'pnl', '0')},
            {sel(col_fee, 'fee_total', '0')},
            {sel(col_partial, 'nb_partial', '0')},
            {sel(col_pyramide, 'nb_pyramide', '0')},
            {sel(col_step, 'close_steps', '1')}
        FROM recorder
        WHERE {col_pnl_net} IS NOT NULL
    """
    rows = c.execute(sql).fetchall()

trades = []
for r in rows:
    entry_reason = r["entry_reason"] or ""
    mode = (r["dec_mode"] or "").strip().upper()
    if not mode and entry_reason:
        mode = entry_reason.split(":", 1)[0].strip().upper()
    if mode in {"", "UNKNOWN", "N/A", "NONE", "NULL"}:
        mode = "UNKNOWN"

    trades.append({
        "uid": r["uid"],
        "inst": r["instId"],
        "side": r["side"],
        "mode": mode,
        "entry": (entry_reason or "UNKNOWN").split(":")[0],
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

