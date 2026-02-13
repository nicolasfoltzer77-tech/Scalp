#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
EXEC — MARKET ADAPTER
- lit v_ticks_latest_spread
- calcule prix exécuté réel (spread + slippage)
- calcule fees Bitget Futures
"""

import sqlite3
from pathlib import Path

from exec_price import compute_exec_price, compute_fee
from exec_slippage import compute_slippage_bps, apply_slippage

ROOT = Path("/opt/scalp/project")
DB_TICKS = ROOT / "data/t.db"

SQL_PRICE = """
SELECT lastPr, spread_bps
FROM v_ticks_latest_spread
WHERE instId=?
LIMIT 1;
"""


def conn():
    c = sqlite3.connect(str(DB_TICKS), timeout=5)
    c.row_factory = sqlite3.Row
    return c


def get_exec_price_and_fee(*, instId, side, qty):
    """
    Retourne (price_exec, fee)
    """
    with conn() as t:
        px = t.execute(SQL_PRICE, (instId,)).fetchone()

    if not px:
        return None, None

    mid = px["lastPr"]
    spread_bps = px["spread_bps"]

    if mid is None or spread_bps is None:
        return None, None

    # --- 1) spread ---
    price = compute_exec_price(
        side=side,
        mid_price=mid,
        spread_bps=spread_bps
    )

    # --- 2) slippage ---
    slip_bps = compute_slippage_bps(spread_bps=spread_bps)
    price = apply_slippage(
        side=side,
        price=price,
        slippage_bps=slip_bps
    )

    # --- 3) fees ---
    fee = compute_fee(
        qty=qty,
        price_exec=price
    )

    return price, fee

