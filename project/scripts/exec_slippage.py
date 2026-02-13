#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
EXEC — SLIPPAGE MODEL (BITGET FUTURES)

- slippage directionnel
- proportionnel au spread
- stochastique borné
- AUCUNE DB
"""

import random

SLIPPAGE_MIN_MULT = 0.10
SLIPPAGE_MAX_MULT = 0.35


def compute_slippage_bps(*, spread_bps):
    """
    Retourne un slippage en bps (>=0)
    """
    if spread_bps is None:
        return 0.0

    try:
        sb = float(spread_bps)
    except Exception:
        return 0.0

    mult = random.uniform(SLIPPAGE_MIN_MULT, SLIPPAGE_MAX_MULT)
    return sb * mult


def apply_slippage(*, side, price, slippage_bps):
    """
    Applique le slippage directionnel
    """
    if price is None:
        return None

    try:
        p = float(price)
    except Exception:
        return None

    try:
        sb = float(slippage_bps)
    except Exception:
        sb = 0.0

    slip_pct = sb / 10_000.0

    if side == "buy":
        return p * (1.0 + slip_pct)
    else:
        return p * (1.0 - slip_pct)

