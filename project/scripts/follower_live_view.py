#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCALP - FOLLOWER LIVE VIEW (READ ONLY)

OBJECTIF :
- Afficher TOUT follower.db (aucun filtrage)
- Distinguer clairement :
  * ouverture en cours (OPEN_PENDING)
  * vrais zombies UID
  * incohérences FSM
- AUCUNE écriture
"""

import sqlite3
import time
from pathlib import Path

ROOT = Path("/opt/scalp/project")

DB_FOLLOWER = ROOT / "data/follower.db"
DB_GEST     = ROOT / "data/gest.db"
DB_EXEC     = ROOT / "data/exec.db"
DB_TICKS    = ROOT / "data/t.db"

REFRESH_S = 1.0

# ============================================================
# SQLITE
# ============================================================

def conn(db):
    c = sqlite3.connect(str(db), timeout=5)
    c.row_factory = sqlite3.Row
    return c

# ============================================================
# LOADERS
# ============================================================

def load_follower():
    c = conn(DB_FOLLOWER)
    rows = c.execute("SELECT * FROM follower").fetchall()
    c.close()
    return {r["uid"]: dict(r) for r in rows}

def load_gest():
    c = conn(DB_GEST)
    rows = c.execute("""
        SELECT uid, instId, side, entry, ts_open, status, atr_signal
        FROM gest
    """).fetchall()
    c.close()
    return {r["uid"]: dict(r) for r in rows}

def load_exec_pos():
    c = conn(DB_EXEC)
    rows = c.execute("""
        SELECT uid, side, qty_open, avg_price_open
        FROM v_exec_position
    """).fetchall()
    c.close()
    return {r["uid"]: dict(r) for r in rows}

def load_ticks():
    c = conn(DB_TICKS)
    rows = c.execute("""
        SELECT instId, lastPr, ts_ms
        FROM ticks
    """).fetchall()
    c.close()
    return {r["instId"]: dict(r) for r in rows}

# ============================================================
# DISPLAY
# ============================================================

def clear():
    print("\033[2J\033[H", end="")

def header():
    print(
        f"{'FLAG':<13} "
        f"{'INST':<12} {'SIDE':<5} "
        f"{'ENTRY':>10} {'NOW':>10} "
        f"{'SL_HARD':>10} {'SL_BE':>10} {'SL_TRAIL':>10} {'TP':>10} "
        f"{'POS_QTY':>12} {'REQ_QTY':>12} "
        f"{'PNL':>8} {'%PNL':>7} "
        f"{'AGE':>6} "
        f"{'ATR':>10} "
        f"{'MFE_ATR':>8} {'MAE_ATR':>8} "
        f"{'F_STATUS':<14} {'G_STATUS':<14} "
        f"{'STEP':>4}"
    )
    print("=" * 216)

def fmt_price(x, digits=4):
    try:
        return f"{float(x):.{digits}f}"
    except Exception:
        return "0.0000"

def fmt_qty(x):
    try:
        return f"{float(x):.4f}"
    except Exception:
        return "0.0000"

def fmt_atr(x):
    try:
        v = float(x)
        if v == 0:
            return "0"
        if abs(v) < 0.001:
            return f"{v:.2e}"
        return f"{v:.4f}"
    except Exception:
        return "0"

def row(flag, inst, side, entry, now,
        sl_hard, sl_be, sl_trail, tp_dyn,
        pos_qty, req_qty,
        pnl, pnl_pct, age, atr, mfe_atr, mae_atr,
        f_status, g_status, step):

    print(
        f"{flag:<13} "
        f"{inst:<12} {side:<5} "
        f"{entry:>10} {now:>10} "
        f"{sl_hard:>10} {sl_be:>10} {sl_trail:>10} {tp_dyn:>10} "
        f"{pos_qty:>12} {req_qty:>12} "
        f"{pnl:>8.2f} {pnl_pct:>7.2f}% "
        f"{age:>6.0f}s "
        f"{atr:>10} "
        f"{mfe_atr:>8.2f} {mae_atr:>8.2f} "
        f"{f_status:<14} {g_status:<14} "
        f"{step:>4}"
    )

# ============================================================
# FLAGGING
# ============================================================

def compute_flag(f_status, g_status, pos_qty, req_qty):
    if g_status in ("open_stdby", "open_done") and pos_qty <= 0:
        return "OPEN_PENDING"

    if f_status == "follow" and g_status == "NO_GEST" and pos_qty <= 0:
        return "ZOMBIE_UID"

    if f_status.endswith("_req") and g_status != f_status:
        return "REQ_NACK"

    if f_status.endswith("_stdby"):
        expected = f_status.replace("_stdby", "_req")
        if g_status != expected:
            return "STDBY_MIS"

    if g_status == "close_done":
        return "GEST_CDONE"

    if f_status in ("partial_req", "pyramide_req", "close_req") and req_qty <= 0:
        return "REQ_Q0"

    return "OK"

# ============================================================
# MAIN
# ============================================================

def main():
    while True:
        clear()

        follower = load_follower()
        gest     = load_gest()
        execpos  = load_exec_pos()
        ticks    = load_ticks()

        header()

        now_ts = int(time.time() * 1000)
        enriched = []

        for uid, f in follower.items():
            g = gest.get(uid)
            e = execpos.get(uid)

            inst = g["instId"] if g else uid[:12]
            side = (
                (g.get("side") if g else None)
                or (e.get("side") if e else None)
                or ("buy" if "-buy-" in uid else "sell" if "-sell-" in uid else "?")
            )
            entry_val = (
                float(e.get("avg_price_open") or 0.0)
                if e else 0.0
            )
            if entry_val <= 0.0 and g and g.get("entry"):
                entry_val = float(g["entry"])

            t = ticks.get(inst)
            now_val = t["lastPr"] if t else entry_val

            pos_qty = float(e["qty_open"]) if e and e["qty_open"] else 0.0
            req_qty = float(f.get("qty_to_close") or 0.0)
            sl_hard = float(f.get("sl_hard") or 0.0)
            sl_be = float(f.get("sl_be") or 0.0)
            sl_trail = float(f.get("sl_trail") or 0.0)
            tp_dyn = float(f.get("tp_dyn") or 0.0)

            pnl = pnl_pct = 0.0
            if pos_qty > 0 and entry_val > 0:
                diff = (now_val - entry_val) if side == "buy" else (entry_val - now_val)
                pnl = diff * pos_qty
                pnl_pct = (diff / entry_val) * 100.0

            age = (now_ts - g["ts_open"]) / 1000.0 if g and g.get("ts_open") else 0.0

            # ATR SAFE
            if g and g.get("atr_signal") is not None:
                atr = float(g["atr_signal"])
            else:
                atr = float(f.get("atr_signal") or 0.0)

            mfe_atr = float(f.get("mfe_atr") or 0.0)
            mae_atr = float(f.get("mae_atr") or 0.0)

            f_status = f.get("status") or "?"
            g_status = g.get("status") if g else "NO_GEST"
            step = int(f.get("step") or 0)

            flag = compute_flag(f_status, g_status, pos_qty, req_qty)
            prio = 0 if flag == "OK" else 1

            enriched.append((prio, -age, flag, inst, side,
                             entry_val, now_val,
                             sl_hard, sl_be, sl_trail, tp_dyn,
                             pos_qty, req_qty,
                             pnl, pnl_pct, age, atr, mfe_atr, mae_atr,
                             f_status, g_status, step))

        enriched.sort()

        for _, _, flag, inst, side, entry, now, sl_hard, sl_be, sl_trail, tp_dyn, pos, req, pnl, pct, age, atr, mfe, mae, fs, gs, step in enriched:
            row(flag, inst, side,
                fmt_price(entry), fmt_price(now),
                fmt_price(sl_hard), fmt_price(sl_be), fmt_price(sl_trail), fmt_price(tp_dyn),
                fmt_qty(pos), fmt_qty(req),
                pnl, pct, age,
                fmt_atr(atr), mfe, mae,
                fs, gs, step)

        time.sleep(REFRESH_S)

if __name__ == "__main__":
    main()
