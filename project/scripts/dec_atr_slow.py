#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DEC — ATR SLOW LOADER
Source : a.db (feat_15m / feat_30m)
"""

import sqlite3
from pathlib import Path

ROOT = Path("/opt/scalp/project")
DB_A = ROOT / "data/a.db"

def conn():
    c = sqlite3.connect(str(DB_A), timeout=5)
    c.row_factory = sqlite3.Row
    return c

def load_atr_slow_map():
    with conn() as c:
        rows = c.execute("""
            SELECT instId,
                   MAX(atr) FILTER (WHERE tf='15m') AS atr_15m,
                   MAX(atr) FILTER (WHERE tf='30m') AS atr_30m
            FROM (
                SELECT instId, atr, '15m' AS tf FROM feat_15m
                UNION ALL
                SELECT instId, atr, '30m' AS tf FROM feat_30m
            )
            GROUP BY instId
        """).fetchall()

    return {r["instId"]: r for r in rows}

