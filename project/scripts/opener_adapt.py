#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
OPENER — ADAPTIVE ADMISSION
- ajuste UNIQUEMENT le ticket d'entrée (STEP 0)
- AUCUNE limite sur les pyramides
"""

import sqlite3
from pathlib import Path

DB_REC = Path("/opt/scalp/project/data/recorder.db")

def conn():
    c = sqlite3.connect(str(DB_REC), timeout=3)
    c.row_factory = sqlite3.Row
    return c


def adaptive_ticket_ratio(instId):
    """
    Retourne ticket_ratio ∈ [0.05 ; 0.10]
    """

    c = conn()
    r = c.execute("""
        SELECT exp, pf
        FROM v_edge_coin
        WHERE instId=?
        LIMIT 1
    """, (instId,)).fetchone()
    c.close()

    # Fallback sécurité
    if not r:
        return 0.05

    exp = r["exp"] or 0.0
    pf  = r["pf"] or 0.0

    # Coin toxique → ticket minimal
    if exp < 0 or pf < 1.0:
        return 0.05

    # Edge faible
    if exp < 0.1 or pf < 1.5:
        return 0.06

    # Edge correct
    if exp < 0.5 or pf < 2.5:
        return 0.08

    # Edge fort
    return 0.10

