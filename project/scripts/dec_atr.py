#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DEC — ATR LOADER + SELECTOR (CANONIQUE / SAFE)

Sources :
- b.db / v_atr_context : ATR rapides (1m / 3m / 5m)
- a.db / feat_15m, feat_30m : ATR lents
"""

import sqlite3
from pathlib import Path

ROOT = Path("/opt/scalp/project")
DB_B = ROOT / "data/b.db"
DB_A = ROOT / "data/a.db"


def conn(p):
    c = sqlite3.connect(str(p), timeout=10)
    c.row_factory = sqlite3.Row
    return c


# --------------------------------------------------
# LOAD ATR MAP (MERGE b.db + a.db)
# --------------------------------------------------
def load_atr_map():
    out = {}

    # --- ATR rapides (b.db)
    with conn(DB_B) as c:
        for r in c.execute("""
            SELECT instId, atr_1m, atr_3m, atr_5m
            FROM v_atr_context
        """):
            out[r["instId"]] = dict(r)

    # --- ATR lents 15m (a.db)
    with conn(DB_A) as c:
        for r in c.execute("""
            SELECT instId, atr AS atr_15m
            FROM feat_15m
            WHERE (instId, ts) IN (
                SELECT instId, MAX(ts)
                FROM feat_15m
                GROUP BY instId
            )
        """):
            out.setdefault(r["instId"], {})["atr_15m"] = r["atr_15m"]

    # --- ATR lents 30m (a.db)
    with conn(DB_A) as c:
        for r in c.execute("""
            SELECT instId, atr AS atr_30m
            FROM feat_30m
            WHERE (instId, ts) IN (
                SELECT instId, MAX(ts)
                FROM feat_30m
                GROUP BY instId
            )
        """):
            out.setdefault(r["instId"], {})["atr_30m"] = r["atr_30m"]

    return out


# --------------------------------------------------
# SELECT ATR PAR PATTERN
# --------------------------------------------------
def select_atr(ctx, atr):
    if not atr:
        return None, None, "UNKNOWN"

    def g(k):
        return atr.get(k)

    if ctx == "MOMENTUM":
        fast, slow = g("atr_1m"), g("atr_5m")
    elif ctx == "PREBREAK":
        fast, slow = g("atr_3m"), g("atr_5m")
    elif ctx == "DRIFT":
        fast, slow = g("atr_5m"), g("atr_15m")
    elif ctx == "CONT":
        fast, slow = g("atr_5m"), g("atr_30m")
    else:
        fast, slow = g("atr_5m"), g("atr_15m")

    if not fast or not slow or slow <= 0:
        return fast, slow, "UNKNOWN"

    ratio = fast / slow
    if ratio < 0.40:
        vol = "COMPRESS"
    elif ratio > 0.75:
        vol = "EXPAND"
    else:
        vol = "NORMAL"

    return fast, slow, vol

