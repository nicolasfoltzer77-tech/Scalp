#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCALP — TRADE CHECK (POST-MORTEM)

But:
- afficher un check COMPLET d'un UID : qty entrée, levier, margin, prix, pnl, fees, steps.
- read-only (aucune écriture DB)
- compatible avec schémas actuels (recorder.db + recorder_steps + exec.db + gest/opener/closer si dispo)
"""

import sys
import sqlite3
from pathlib import Path
from typing import Optional

ROOT = Path("/opt/scalp/project")

DB_REC  = ROOT / "data/recorder.db"
DB_EXEC = ROOT / "data/exec.db"
DB_GEST = ROOT / "data/gest.db"
DB_OPN  = ROOT / "data/opener.db"
DB_CLS  = ROOT / "data/closer.db"


def conn(p: Path) -> sqlite3.Connection:
    c = sqlite3.connect(str(p), timeout=5)
    c.row_factory = sqlite3.Row
    return c


def q1(c: sqlite3.Connection, sql: str, params=()) -> Optional[sqlite3.Row]:
    return c.execute(sql, params).fetchone()


def qall(c: sqlite3.Connection, sql: str, params=()):
    return c.execute(sql, params).fetchall()


def fmt(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.10g}"
    return str(v)


def print_kv(title: str, row: sqlite3.Row, keys):
    print(title)
    print("-" * len(title))
    for k in keys:
        if k in row.keys():
            print(f"{k:18s} : {fmt(row[k])}")
    print()


def try_open(path: Path) -> Optional[sqlite3.Connection]:
    try:
        if not path.exists():
            return None
        return conn(path)
    except Exception:
        return None


def main():
    if len(sys.argv) < 2:
        print("Usage: trade_check.py <UID> [UID2 ...]")
        sys.exit(2)

    uids = sys.argv[1:]

    c_rec  = try_open(DB_REC)
    c_exec = try_open(DB_EXEC)
    c_gest = try_open(DB_GEST)
    c_opn  = try_open(DB_OPN)
    c_cls  = try_open(DB_CLS)

    for uid in uids:
        print("=" * 86)
        print(f"UID: {uid}")
        print("=" * 86)

        # ---------------- RECORDER (trade-level) ----------------
        if c_rec:
            r = q1(c_rec, "SELECT * FROM recorder WHERE uid=? LIMIT 1", (uid,))
            if r:
                keys = [
                    "instId", "side",
                    "ts_signal", "price_signal", "entry_reason", "type_signal",
                    "score_C", "score_S", "score_H", "score_M",
                    "ts_open", "entry", "qty", "lev", "margin",
                    "ts_close", "price_close", "price_exec_close", "reason_close",
                    "pnl", "pnl_pct", "pnl_net",
                    "fee", "fee_total", "pnl_realized",
                    "close_steps", "nb_partial", "nb_pyramide",
                    "atr_signal",
                    "mfe_price", "mfe_ts", "mae_price", "mae_ts",
                    "mfe_atr", "mae_atr",
                    "golden", "golden_ts",
                    "trigger_type", "dec_mode", "dec_ctx", "dec_score_C",
                    "momentum_ok", "prebreak_ok", "pullback_ok", "compression_ok",
                    "ts_recorded",
                ]
                print_kv("RECORDER", r, keys)
            else:
                print("RECORDER\n--------\n(no row)\n")

            # --------------- RECORDER_STEPS (structure) ---------------
            rs = qall(c_rec, """
                SELECT uid, step, exec_type, reason, price_exec, qty_exec, ts_exec,
                       sl_be, sl_trail, tp_dyn, mfe_atr, mae_atr, golden
                FROM recorder_steps
                WHERE uid=?
                ORDER BY step ASC
            """, (uid,))
            print("RECORDER_STEPS")
            print("--------------")
            if not rs:
                print("(none)\n")
            else:
                hdr = ["step","exec_type","reason","price_exec","qty_exec","ts_exec","sl_be","sl_trail","tp_dyn","mfe_atr","mae_atr","golden"]
                print(" | ".join(f"{h:>10s}" for h in hdr))
                print("-" * (13 * len(hdr)))
                for row in rs:
                    vals = [
                        row["step"], row["exec_type"], row["reason"],
                        row["price_exec"], row["qty_exec"], row["ts_exec"],
                        row["sl_be"], row["sl_trail"], row["tp_dyn"],
                        row["mfe_atr"], row["mae_atr"], row["golden"],
                    ]
                    print(" | ".join(f"{fmt(v):>10s}" for v in vals))
                print()

        # ---------------- EXEC (ledger facts) ----------------
        if c_exec:
            ex = qall(c_exec, """
                SELECT exec_id, uid, step, exec_type, side, qty, price_exec, fee, status, ts_exec,
                       instId, lev, pnl_realized_step, reason
                FROM exec
                WHERE uid=?
                ORDER BY ts_exec ASC, step ASC
            """, (uid,))
            print("EXEC (exec.db)")
            print("------------")
            if not ex:
                print("(none)\n")
            else:
                hdr = ["ts_exec","step","exec_type","side","qty","price_exec","fee","pnl_realized_step","lev","status","reason"]
                print(" | ".join(f"{h:>14s}" for h in hdr))
                print("-" * (18 * len(hdr)))
                for row in ex:
                    vals = [
                        row["ts_exec"], row["step"], row["exec_type"], row["side"],
                        row["qty"], row["price_exec"], row["fee"],
                        row["pnl_realized_step"], row["lev"], row["status"], row["reason"],
                    ]
                    print(" | ".join(f"{fmt(v):>14s}" for v in vals))
                print()

        # ---------------- GEST (state) ----------------
        if c_gest:
            g = q1(c_gest, "SELECT * FROM gest WHERE uid=? LIMIT 1", (uid,))
            print("GEST (gest.db)")
            print("-------------")
            if not g:
                print("(none)\n")
            else:
                # affiche un sous-ensemble sûr (colonnes existent souvent)
                wanted = [
                    "instId","side","status","step","qty","qty_to_close",
                    "entry","price_signal","ts_signal",
                    "sl_be","sl_trail","tp_dyn",
                    "mfe_atr","mae_atr","golden","type_signal","dec_mode","reason",
                    "last_action_ts",
                ]
                for k in wanted:
                    if k in g.keys():
                        print(f"{k:18s} : {fmt(g[k])}")
                print()

        # ---------------- OPENER / CLOSER (queues) ----------------
        if c_opn:
            o = qall(c_opn, """
                SELECT uid, instId, side, qty, lev, status, exec_type, step, price_exec_open, ts_open
                FROM opener
                WHERE uid=?
                ORDER BY step ASC
            """, (uid,))
            print("OPENER (opener.db)")
            print("-----------------")
            if not o:
                print("(none)\n")
            else:
                hdr = ["step","exec_type","status","qty","lev","price_exec_open","ts_open"]
                print(" | ".join(f"{h:>14s}" for h in hdr))
                print("-" * (18 * len(hdr)))
                for row in o:
                    vals = [
                        row["step"], row["exec_type"], row["status"],
                        row["qty"], row["lev"], row["price_exec_open"], row["ts_open"],
                    ]
                    print(" | ".join(f"{fmt(v):>14s}" for v in vals))
                print()

        if c_cls:
            cl = qall(c_cls, """
                SELECT uid, instId, side, qty, status, step
                FROM closer
                WHERE uid=?
                ORDER BY step ASC
            """, (uid,))
            print("CLOSER (closer.db)")
            print("-----------------")
            if not cl:
                print("(none)\n")
            else:
                hdr = ["step","status","qty","side"]
                print(" | ".join(f"{h:>12s}" for h in hdr))
                print("-" * (16 * len(hdr)))
                for row in cl:
                    vals = [row["step"], row["status"], row["qty"], row["side"]]
                    print(" | ".join(f"{fmt(v):>12s}" for v in vals))
                print()

    for c in (c_rec, c_exec, c_gest, c_opn, c_cls):
        try:
            if c:
                c.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()

