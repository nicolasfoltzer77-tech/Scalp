#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
EXEC — MARKET ADAPTER
- lit v_ticks_latest_spread si dispo
- sinon fallback v_ticks_latest (lastPr uniquement)
- calcule prix exécuté (spread + slippage)
- calcule fees Bitget Futures (taker)

Note:
- Ce module ne touche AUCUNE DB en écriture.
- Il est optionnel: exec.py peut fallback si ce module ne donne pas de prix.
"""

import sqlite3
from pathlib import Path

from exec_price import compute_exec_price, compute_fee
from exec_slippage import compute_slippage_bps, apply_slippage

ROOT = Path("/opt/scalp/project")
DB_TICKS = ROOT / "data/t.db"


def conn():
    c = sqlite3.connect(str(DB_TICKS), timeout=5)
    c.row_factory = sqlite3.Row
    return c


def _has_view(c, name: str) -> bool:
    r = c.execute(
        "SELECT 1 FROM sqlite_master WHERE (type='view' OR type='table') AND name=? LIMIT 1",
        (name,)
    ).fetchone()
    return bool(r)


def get_exec_price_and_fee(*, instId, side, qty):
    """
    Retourne (price_exec, fee) ou (None, None)
    """
    if not instId or side not in ("buy", "sell"):
        return None, None

    with conn() as t:
        if _has_view(t, "v_ticks_latest_spread"):
            row = t.execute("""
                SELECT lastPr, spread_bps
                FROM v_ticks_latest_spread
                WHERE instId=?
                LIMIT 1;
            """, (instId,)).fetchone()

            if not row:
                return None, None

            mid = row["lastPr"]
            spread_bps = row["spread_bps"]

            if mid is None:
                return None, None

            # spread: mid -> bid/ask
            price = compute_exec_price(side=side, mid_price=float(mid), spread_bps=spread_bps)

            # slippage
            slip_bps = compute_slippage_bps(spread_bps=spread_bps)
            price = apply_slippage(side=side, price=price, slippage_bps=slip_bps)

            # fees
            fee = compute_fee(qty=qty, price_exec=price)
            return float(price), float(fee)

        # fallback: v_ticks_latest lastPr
        if _has_view(t, "v_ticks_latest"):
            row = t.execute("""
                SELECT lastPr
                FROM v_ticks_latest
                WHERE instId=?
                LIMIT 1;
            """, (instId,)).fetchone()

            if not row or row["lastPr"] is None:
                return None, None

            price = float(row["lastPr"])
            fee = compute_fee(qty=qty, price_exec=price)
            return float(price), float(fee)

    return None, None

