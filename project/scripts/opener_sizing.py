#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def compute_ticket_qty(*, balance_usdt, price, score_C, score_S, score_H,
                       market_risk, ticket_ratio):
    """
    Modèle de sizing (inchangé)
    """
    score = clamp(
        ((abs(score_C) + score_S) / 2.0) * (0.5 + score_H),
        0.0,
        1.0
    )

    margin_pct  = 0.01 + score * 0.09
    margin_usdt = balance_usdt * margin_pct
    lev         = int(round(1 + score * 19))

    risk = clamp(market_risk, 0.3, 1.0)
    lev  = max(1, int(lev * risk))

    qty_nominal = (margin_usdt * lev * risk) / price
    qty_ticket  = qty_nominal * ticket_ratio

    return qty_ticket, lev, score


# ============================================================
# 🔥 EXCHANGE FLOOR + CONTRACT VALIDATION (UPGRADE SAFE)
# ============================================================

def apply_contract_constraints(qty, price, contract):
    """
    Respect strict contraintes exchange.
    Retourne qty_final ou 0 si non tradable.
    """
    if not contract:
        return qty

    min_qty   = float(contract["minTradeNum"])
    step_size = float(contract["sizeMultiplier"])
    min_usdt  = float(contract["minTradeUSDT"])

    # --- FLOOR NOTIONAL (nouveau comportement critique) ---
    qty_floor = min_usdt / price
    if qty < qty_floor:
        qty = qty_floor

    # --- ARRONDI STEP ---
    qty = (qty // step_size) * step_size

    # --- MIN QTY ---
    if qty < min_qty:
        return 0.0

    # --- NOTIONAL CHECK FINAL ---
    if qty * price < min_usdt:
        return 0.0

    return qty

