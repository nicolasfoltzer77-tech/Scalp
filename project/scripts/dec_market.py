#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DEC — MARKET VETO
Source : market.db / v_market_latest
"""

import sqlite3
from pathlib import Path

ROOT = Path("/opt/scalp/project")
DB_MARKET = ROOT / "data/market.db"

def conn():
    c = sqlite3.connect(str(DB_MARKET), timeout=10)
    c.row_factory = sqlite3.Row
    return c

def load_market_ok():
    with conn() as c:
        return {
            r["instId"]: r
            for r in c.execute("""
                SELECT instId, ticks_5s, spread_bps, staleness_ms
                FROM v_market_latest
                WHERE market_ok = 1
            """)
        }

def market_pass(m, cfg):
    return not (
        m["ticks_5s"]   < cfg["min_ticks_5s"]
        or m["spread_bps"] > cfg["max_spread_bps"]
        or m["staleness_ms"] > cfg["max_staleness_ms"]
    )

