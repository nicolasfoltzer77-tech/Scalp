#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DEC — ATR FAST / SLOW SELECTOR (CANONIQUE)

- Source : b.db / v_atr_context (READ-ONLY)
- Sélection ATR par pattern (ctx)
- Calcul régime de volatilité
- AUCUN recalcul d’indicateur
- SAFE si colonnes manquantes
"""

import sqlite3
from pathlib import Path

ROOT = Path("/opt/scalp/project")
DB_B = ROOT / "data/b.db"

# ------------------------------------------------------------
# SQLITE CONN
# ------------------------------------------------------------
def conn():
    c = sqlite3.connect(str(DB_B), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c

# ------------------------------------------------------------
# LOAD ATR MAP
# ------------------------------------------------------------
def load_atr_map():
    """
    Charge v_atr_context
    Retour : dict instId -> sqlite3.Row
    """
    with conn() as c:
        rows = c.execute("""
            SELECT *
            FROM v_atr_context
        """).fetchall()

    return {r["instId"]: r for r in rows}

# ------------------------------------------------------------
# SAFE ACCESS
# ------------------------------------------------------------
def _get(r, k):
    return r[k] if r and k in r.keys() else None

# ------------------------------------------------------------
# ATR SELECTION (PAR PATTERN)
# ------------------------------------------------------------
def select_atr(ctx, atr):
    """
    ctx : string (MOMENTUM / PREBREAK / DRIFT / CONT / autre)
    atr : sqlite3.Row depuis v_atr_context
    """

    if not atr:
        return None, None, "UNKNOWN"

    # ---------------------------
    # Mapping ATR fast / slow
    # ---------------------------
    if ctx == "MOMENTUM":
        fast = _get(atr, "atr_1m")
        slow = _get(atr, "atr_5m")

    elif ctx == "PREBREAK":
        fast = _get(atr, "atr_3m")
        slow = _get(atr, "atr_5m")

    elif ctx == "DRIFT":
        fast = _get(atr, "atr_5m")
        slow = _get(atr, "atr_15m")

    elif ctx == "CONT":
        fast = _get(atr, "atr_5m")
        slow = _get(atr, "atr_30m")

    else:
        fast = _get(atr, "atr_5m")
        slow = _get(atr, "atr_15m")

    # ---------------------------
    # Volatility regime
    # ---------------------------
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


