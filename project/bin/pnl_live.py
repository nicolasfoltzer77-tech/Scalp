#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3, time, os

DB_G = "/opt/scalp/project/data/gest.db"
DB_T = "/opt/scalp/project/data/t.db"
DB_F = "/opt/scalp/project/data/follower.db"

def conn(path):
    c = sqlite3.connect(path, timeout=2, isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=2000;")
    return c

# ---------------------------------------
# TICKS
# ---------------------------------------
def get_ticks():
    con = conn(DB_T)
    rows = con.execute("SELECT instId, lastPr FROM v_ticks_latest;").fetchall()
    con.close()
    return {inst: price for inst, price in rows}

# ---------------------------------------
# TRADES EN COURS (gest)
# ---------------------------------------
def get_trades():
    con = conn(DB_G)
    rows = con.execute("""
    SELECT uid, instId, side, entry, qty, lev, margin, ts_open, status
    FROM trades
    WHERE status='opened' OR status='follow';
    """).fetchall()
    con.close()
    return rows

# ---------------------------------------
# SL/TP dynamiques (follower)
# ---------------------------------------
def get_dyn(uid):
    con = conn(DB_F)
    row = con.execute("""
        SELECT sl_be, sl_trail, tp_dyn, price_to_close
        FROM trades_follow
        WHERE uid=? AND status='follow'
        LIMIT 1;
    """,(uid,)).fetchone()
    con.close()

    if row is None:
        return None, None, None, None
    return row

# ---------------------------------------
# PNL
# ---------------------------------------
def compute_pnl(side, entry, qty, last):
    if last is None:
        return 0.0, 0.0

    if side == "buy":
        pnl = (last - entry) * qty
    else:
        pnl = (entry - last) * qty

    pct = (pnl / (entry * qty) * 100) if entry > 0 else 0
    return pnl, pct


# ---------------------------------------
# MAIN LOOP — refresh 1s
# ---------------------------------------
def main():

    while True:
        os.system("clear")

        ticks = get_ticks()
        trades = get_trades()

        print("")
        print("==============================================")
        print("          TRADES EN COURS — PnL LIVE          ")
        print("==============================================\n")

        print("{:23} {:10} {:5} {:10} {:10} {:10} {:10} {:10}".format(
            "uid", "instId", "side", "last", "pnl_usdt",
            "pnl_pct", "sl_dyn", "tp_dyn"
        ))
        print("-"*95)

        for uid, instId, side, entry, qty, lev, margin, ts_open, status in trades:

            inst_plain = instId.replace("/", "")
            last = ticks.get(inst_plain)

            pnl_usdt, pnl_pct = compute_pnl(side, entry, qty, last)

            sl_be, sl_trail, tp_dyn, price_to_close = get_dyn(uid)

            # sl_dyn = sl_trail (s'il existe), sinon sl_be
            sl_dyn = sl_trail if sl_trail else sl_be

            print("{:23} {:10} {:5} {:10.4f} {:10.4f} {:10.2f} {:10} {:10}".format(
                uid,
                instId,
                side,
                last if last else 0,
                pnl_usdt,
                pnl_pct,
                f"{sl_dyn:.4f}" if sl_dyn else "-",
                f"{tp_dyn:.4f}" if tp_dyn else "-"
            ))

        print("\n(rafraîchissement : 1 seconde)")
        time.sleep(1)


if __name__ == "__main__":
    main()

