#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DEC — CTX MICRO READER
Source : a.db / v_ctx_signal
"""

import sqlite3
from pathlib import Path

ROOT = Path("/opt/scalp/project")
DB_A = ROOT / "data/a.db"

def conn():
    c = sqlite3.connect(str(DB_A), timeout=10)
    c.row_factory = sqlite3.Row
    return c

def load_ctx():
    with conn() as c:
        return c.execute("""
            SELECT instId, ctx, score_C, side
            FROM v_ctx_signal
            WHERE ctx_ok = 1
        """).fetchall()

