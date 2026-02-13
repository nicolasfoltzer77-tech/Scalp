#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
EXEC — PRICE & COST ENGINE (BITGET FUTURES)

Responsabilité UNIQUE :
- transformer un prix mid en prix exécuté réel (spread)
- calculer les fees Bitget Futures (taker)
- AUCUNE logique FSM
- AUCUNE écriture DB
"""

BITGET_TAKER_FEE = 0.0006   # 0.06% futures taker


def compute_exec_price(*, side, mid_price, spread_bps):
    """
    side        : 'buy' | 'sell'
    mid_price  : prix mid marché
    spread_bps : spread bid/ask en basis points (bps)
    """
    if mid_price is None:
        return None

    if spread_bps is None:
        return float(mid_price)

    spread_pct = float(spread_bps) / 10_000.0
    half = spread_pct / 2.0

    if side == "buy":
        return float(mid_price) * (1.0 + half)
    else:
        return float(mid_price) * (1.0 - half)


def compute_notional(*, qty, price_exec):
    if qty is None or price_exec is None:
        return 0.0
    return abs(float(qty) * float(price_exec))


def compute_fee(*, qty, price_exec):
    """
    Fee Bitget futures taker
    Levier déjà inclus implicitement via qty
    """
    notional = compute_notional(qty=qty, price_exec=price_exec)
    return notional * BITGET_TAKER_FEE

