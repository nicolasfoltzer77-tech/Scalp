#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RECORDER — ANALYSE STEP 1 (ADMISSION ONLY)
"""

import sqlite3
from pathlib import Path

DB = Path("/opt/scalp/project/data/recorder.db")

def conn():
    c = sqlite3.connect(str(DB))
    c.row_factory = sqlite3.Row
    return c

def fmt(v):
    return f"{v:+.4f}" if v is not None else "N/A"

with conn() as c:
    cols = {r["name"] for r in c.execute("PRAGMA table_info(recorder)").fetchall()}
    pnl_col = "pnl_realized"
    for candidate in ("pnl_realized", "pnl_net", "pnl"):
        if candidate in cols:
            pnl_col = candidate
            break

    rows = c.execute("""
        SELECT
            r.uid,
            r.{pnl_col} AS pnl,
            rs.mfe_atr,
            rs.mae_atr
        FROM recorder r
        JOIN recorder_steps rs USING(uid)
        WHERE rs.step = 1
          AND rs.exec_type = 'close'
    """.format(pnl_col=pnl_col)).fetchall()

tox = [r for r in rows if r["mfe_atr"] is not None and r["mfe_atr"] < 0.3]
ok = [r for r in rows if r not in tox]

print("\nSTEP 1 — ADMISSION STRICTE")
print("=" * 60)
print(f"Trades STEP 1 : {len(rows)}")
print(f"Toxiques      : {len(tox)}")
print(f"Sains         : {len(ok)}")

print("\nDÉTAIL")
print("-" * 60)
print(f"Toxiques | exp={fmt(sum(r['pnl'] for r in tox)/len(tox) if tox else None)}")
print(f"Sains    | exp={fmt(sum(r['pnl'] for r in ok)/len(ok) if ok else None)}")
