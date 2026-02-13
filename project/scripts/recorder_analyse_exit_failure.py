#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RECORDER — EXIT FAILURE ANALYSER (DESK-GRADE / TIMED / FSM-AWARE)

UPGRADE :
- distinction claire STEP 1 vs STEP >=2
- DRIFT / early trades analysés comme ADMISSION failures
- lock-in failure réservé aux trades exploités
"""

import argparse
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
    if v is None:
        return "NA"
    if isinstance(v, float):
        return f"{v:+.{n}f}"
    return str(v)

def fmt_s(v):
    if v is None:
        return "NA"
    return f"{v:.1f}s"

def exit_family(reason):
    r = (reason or "").upper()
    if "TIME" in r:
        return "TIME"
    if "TP" in r:
        return "TP"
    if "SL" in r:
        return "SL"
    return "OTHER"

# ============================================================
# LOAD
# ============================================================

def load_trades(c):
    return c.execute("""
        SELECT
            uid, instId, side,
            pnl_realized,
            mfe_atr, mae_atr,
            nb_partial, nb_pyramide,
            reason_close,
            type_signal, dec_mode,
            ts_open, ts_close
        FROM recorder
        ORDER BY ts_open
    """).fetchall()

def load_steps(c):
    rows = c.execute("""
        SELECT uid, step, exec_type, reason,
               mfe_atr, mae_atr, ts_exec
        FROM recorder_steps
        ORDER BY uid, ts_exec
    """).fetchall()
    out = {}
    for r in rows:
        out.setdefault(r["uid"], []).append(r)
    return out

# ============================================================
# CORE
# ============================================================

def compute_peak(steps):
    peak = None
    ts_peak = None
    step_peak = None
    for s in steps:
        if s["mfe_atr"] is None:
            continue
        if peak is None or s["mfe_atr"] > peak:
            peak = float(s["mfe_atr"])
            ts_peak = s["ts_exec"]
            step_peak = s["step"]
    return peak, ts_peak, step_peak

def classify(trade, steps, admit_mfe, lock_mfe):
    pnl = trade["pnl_realized"]
    mfe_peak, ts_peak, step_peak = compute_peak(steps)
    step_final = max((s["step"] for s in steps), default=0)

    tags = []

    # ---------------- STEP 1 ONLY ----------------
    if step_final <= 1:
        if mfe_peak is None or mfe_peak < admit_mfe:
            tags.append("ADMISSION_FAIL_EARLY")
        else:
            tags.append("ADMISSION_FAIL_TIMEOUT")
        return tags, mfe_peak, ts_peak, step_peak

    # ---------------- EXPLOITATION ----------------
    tags.append("ADMITTED")

    if mfe_peak is not None and mfe_peak >= lock_mfe and pnl < 0:
        tags.append("LOCKIN_FAILURE")

    if trade["nb_pyramide"] >= 2 and pnl < 0:
        tags.append("PYR_RISK")

    return tags, mfe_peak, ts_peak, step_peak

# ============================================================
# REPORT
# ============================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uid", help="UID à détailler")
    ap.add_argument("--admit-mfe", type=float, default=0.30)
    ap.add_argument("--lock-mfe", type=float, default=1.00)
    args = ap.parse_args()

    with conn() as c:
        trades = load_trades(c)
        steps = load_steps(c)

    rows = []

    for t in trades:
        uid = t["uid"]
        st = steps.get(uid, [])
        tags, mfe_peak, ts_peak, step_peak = classify(t, st, args.admit_mfe, args.lock_mfe)

        rows.append({
            "uid": uid,
            "inst": t["instId"],
            "side": t["side"],
            "pnl": t["pnl_realized"],
            "mfe_peak": mfe_peak,
            "tags": tags,
            "nb_pyr": t["nb_pyramide"],
            "nb_part": t["nb_partial"],
            "entry": t["dec_mode"]
        })

    # ========================================================
    # WORST STEP 1
    # ========================================================

    print("\nWORST STEP 1 — ADMISSION FAILURES")
    print("=" * 60)

    bad = [r for r in rows if "ADMISSION_FAIL" in ",".join(r["tags"])]
    bad = sorted(bad, key=lambda x: x["pnl"])

    for r in bad[:10]:
        print(
            f"{r['uid']:<28s} "
            f"{r['inst']:<8s} "
            f"pnl={r['pnl']:+.2f} "
            f"mfe_peak={fmt(r['mfe_peak'],2):>6s} "
            f"tags={','.join(r['tags'])} "
            f"entry={r['entry']}"
        )

    # ========================================================
    # DETAIL UID
    # ========================================================

    if args.uid:
        hit = next((r for r in rows if r["uid"] == args.uid), None)
        if not hit:
            print("UID introuvable")
            return

        print("\nDETAIL TRADE")
        print("=" * 60)
        for k, v in hit.items():
            print(f"{k:12s}: {v}")

if __name__ == "__main__":
    main()

