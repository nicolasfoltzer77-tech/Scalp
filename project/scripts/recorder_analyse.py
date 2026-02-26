#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RECORDER — ANALYSE GLOBALE AVANCÉE

Inclut :
- performance globale
- répartition par mode d'entrée
- analyse par levier
- analyse par step final
- analyse détaillée des executions `recorder_steps` (open/partial/pyramide/close)
- croisements mode × levier × step
- best / worst trades enrichis
"""

import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
DB_CANDIDATES = [
    ROOT / "data/recorder.db",
    Path("/opt/scalp/project/data/recorder.db"),
]


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


def winrate(pnls):
    if not pnls:
        return 0.0
    return sum(1 for p in pnls if p > 0) / len(pnls)


def fmt(v, n=4):
    return f"{v:+.{n}f}"


def lev_bucket(v):
    if v is None:
        return "UNK"
    if v < 5:
        return "<5"
    if v < 10:
        return "5-9"
    if v < 20:
        return "10-19"
    return "20+"


# ============================================================
# LOAD RECORDER
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
    col_lev = first_col(cols, ["lev", "leverage"])

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
            {sel(col_step, 'close_steps', '1')},
            {sel(col_lev, 'lev', 'NULL')}
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

    lev = float(r["lev"]) if r["lev"] is not None else None

    trades.append(
        {
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
            "lev": lev,
            "lev_bucket": lev_bucket(lev),
        }
    )

trades_by_uid = {t["uid"]: t for t in trades}

# ============================================================
# LOAD RECORDER_STEPS
# ============================================================

step_rows = []
with conn() as c:
    tables = {
        r["name"]
        for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if "recorder_steps" in tables:
        s_cols = table_columns(c, "recorder_steps")
        mandatory = {"uid", "step", "exec_type"}
        if mandatory.issubset(s_cols):
            step_rows = c.execute(
                """
                SELECT
                    uid,
                    step,
                    exec_type,
                    reason,
                    price_exec,
                    qty_exec,
                    ts_exec,
                    mfe_atr,
                    mae_atr,
                    golden
                FROM recorder_steps
                ORDER BY uid, step
                """
            ).fetchall()

steps_by_uid = defaultdict(list)
for r in step_rows:
    steps_by_uid[r["uid"]].append(
        {
            "step": int(r["step"]),
            "exec_type": (r["exec_type"] or "").lower(),
            "reason": r["reason"] or "",
            "price_exec": r["price_exec"],
            "qty_exec": r["qty_exec"],
            "ts_exec": r["ts_exec"],
            "mfe_atr": r["mfe_atr"],
            "mae_atr": r["mae_atr"],
            "golden": int(r["golden"] or 0),
        }
    )

# ============================================================
# GLOBAL
# ============================================================

print("\nRÉSUMÉ GLOBAL")
print("=" * 80)

pnls = [t["pnl_net"] for t in trades]

print(f"DB            : {DB}")
print(f"Trades        : {len(trades)}")
print(f"PNL net total : {sum(pnls):+.4f}")
print(f"PNL net moyen : {fmt(avg(pnls))}")
print(f"Winrate       : {winrate(pnls) * 100:.2f}%")
print(f"Profit factor : {pf(pnls):.2f}")
print(f"Steps rows    : {len(step_rows)}")

# ============================================================
# RÉPARTITION PAR MODE
# ============================================================

print("\nRÉPARTITION — TYPE D’ENTRÉE (dec_mode)")
print("=" * 80)

by_mode = defaultdict(list)
for t in trades:
    by_mode[t["mode"]].append(t["pnl_net"])

for mode, xs in sorted(by_mode.items(), key=lambda x: avg(x[1]), reverse=True):
    print(
        f"{mode:12s} | n={len(xs):4d} | win={winrate(xs) * 100:6.2f}% "
        f"| exp={fmt(avg(xs))} | pf={pf(xs):.2f}"
    )

# ============================================================
# RÉPARTITION PAR LEVIER
# ============================================================

print("\nRÉPARTITION — LEVIER")
print("=" * 80)

by_lev = defaultdict(list)
for t in trades:
    by_lev[t["lev_bucket"]].append(t["pnl_net"])

for bucket in ["<5", "5-9", "10-19", "20+", "UNK"]:
    xs = by_lev.get(bucket, [])
    if not xs:
        continue
    print(
        f"{bucket:6s} | n={len(xs):4d} | win={winrate(xs) * 100:6.2f}% "
        f"| exp={fmt(avg(xs))} | pf={pf(xs):.2f}"
    )

# ============================================================
# TYPE D’ENTRÉE × STEP FINAL × LEVIER
# ============================================================

print("\nTYPE D’ENTRÉE × STEP FINAL × LEVIER")
print("=" * 80)

grid = defaultdict(list)
for t in trades:
    key = (t["mode"], t["step"], t["lev_bucket"])
    grid[key].append(t["pnl_net"])

for (mode, step, bucket), xs in sorted(grid.items()):
    if len(xs) < 3:
        continue
    print(
        f"{mode:12s} | step={step:<2d} | lev={bucket:5s} | n={len(xs):4d} "
        f"| win={winrate(xs) * 100:6.2f}% | exp={fmt(avg(xs))} | pf={pf(xs):.2f}"
    )

# ============================================================
# ANALYSE recorder_steps
# ============================================================

print("\nANALYSE recorder_steps")
print("=" * 80)

if not step_rows:
    print("Aucune donnée recorder_steps disponible.")
else:
    exec_counter = Counter()
    reason_counter = Counter()
    close_reason_counter = Counter()

    by_exec = defaultdict(list)
    by_exec_lev = defaultdict(list)
    golden_pnls = []
    nongolden_pnls = []
    close_mfe = []
    close_mae = []

    for uid, entries in steps_by_uid.items():
        trade = trades_by_uid.get(uid)
        if not trade:
            continue
        pnl = trade["pnl_net"]
        bucket = trade["lev_bucket"]

        for e in entries:
            exec_counter[e["exec_type"]] += 1
            if e["reason"]:
                reason_counter[e["reason"]] += 1

            by_exec[e["exec_type"]].append(pnl)
            by_exec_lev[(e["exec_type"], bucket)].append(pnl)

            if e["golden"]:
                golden_pnls.append(pnl)
            else:
                nongolden_pnls.append(pnl)

            if e["exec_type"] == "close":
                if e["reason"]:
                    close_reason_counter[e["reason"]] += 1
                if e["mfe_atr"] is not None:
                    close_mfe.append(float(e["mfe_atr"]))
                if e["mae_atr"] is not None:
                    close_mae.append(float(e["mae_atr"]))

    print("Exec types (volume d'events):")
    for exec_type, n in exec_counter.most_common():
        print(f"  - {exec_type:10s}: {n}")

    print("\nImpact net par exec_type (sur trades contenant l'event):")
    for exec_type, xs in sorted(by_exec.items(), key=lambda x: avg(x[1]), reverse=True):
        print(
            f"  - {exec_type:10s} | n={len(xs):4d} | win={winrate(xs) * 100:6.2f}% "
            f"| exp={fmt(avg(xs))} | pf={pf(xs):.2f}"
        )

    print("\nClose reasons (top 10):")
    for reason, n in close_reason_counter.most_common(10):
        print(f"  - {reason:20s}: {n}")

    print("\nImpact exec_type × levier (n>=3):")
    for (exec_type, bucket), xs in sorted(by_exec_lev.items()):
        if len(xs) < 3:
            continue
        print(
            f"  - {exec_type:10s} | lev={bucket:5s} | n={len(xs):4d} "
            f"| exp={fmt(avg(xs))} | pf={pf(xs):.2f}"
        )

    if close_mfe or close_mae:
        print("\nStats close ATR:")
        if close_mfe:
            print(f"  - mfe_atr moyen : {avg(close_mfe):.4f}")
        if close_mae:
            print(f"  - mae_atr moyen : {avg(close_mae):.4f}")

    if golden_pnls and nongolden_pnls:
        print("\nComparatif golden flag:")
        print(
            f"  - golden=1 | n={len(golden_pnls):4d} | exp={fmt(avg(golden_pnls))} "
            f"| pf={pf(golden_pnls):.2f}"
        )
        print(
            f"  - golden=0 | n={len(nongolden_pnls):4d} | exp={fmt(avg(nongolden_pnls))} "
            f"| pf={pf(nongolden_pnls):.2f}"
        )

# ============================================================
# EDGE NET — PAR COIN
# ============================================================

print("\nEDGE NET — PAR COIN")
print("=" * 80)

by_inst = defaultdict(list)
for t in trades:
    by_inst[t["inst"]].append(t["pnl_net"])

for inst, xs in sorted(by_inst.items(), key=lambda x: avg(x[1]), reverse=True):
    if len(xs) >= 3:
        print(
            f"{inst:12s} | n={len(xs):4d} | win={winrate(xs) * 100:6.2f}% "
            f"| exp={fmt(avg(xs))} | pf={pf(xs):.2f}"
        )

# ============================================================
# BEST / WORST TRADES
# ============================================================

print("\nBEST 5 TRADES (PNL NET)")
print("=" * 80)

for t in sorted(trades, key=lambda x: x["pnl_net"], reverse=True)[:5]:
    print(
        f"{t['uid']} {t['inst']} {t['side']} "
        f"| net={fmt(t['pnl_net'])} brut={fmt(t['pnl'])} "
        f"fees={fmt(-t['fees'])} "
        f"| step={t['step']} lev={t['lev'] if t['lev'] is not None else 'NA'} "
        f"pyr={t['pyramide']} part={t['partial']} "
        f"| mode={t['mode']}"
    )

print("\nWORST 5 TRADES (PNL NET)")
print("=" * 80)

for t in sorted(trades, key=lambda x: x["pnl_net"])[:5]:
    print(
        f"{t['uid']} {t['inst']} {t['side']} "
        f"| net={fmt(t['pnl_net'])} brut={fmt(t['pnl'])} "
        f"fees={fmt(-t['fees'])} "
        f"| step={t['step']} lev={t['lev'] if t['lev'] is not None else 'NA'} "
        f"pyr={t['pyramide']} part={t['partial']} "
        f"| mode={t['mode']}"
    )
