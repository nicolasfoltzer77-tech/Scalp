#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import math

def normalize_qty(*, qty_raw, price, contract):
    """
    contract : row contracts.db
    """

    if qty_raw <= 0:
        return None

    min_qty = contract["minTradeNum"]
    step    = contract["sizeMultiplier"]
    vol_dec = contract["volumePlace"]
    min_usd = contract["minTradeUSDT"]
    max_qty = contract["maxOrderQty"]

    # arrondi step
    qty = math.floor(qty_raw / step) * step
    qty = round(qty, vol_dec)

    if qty < min_qty:
        return None

    if qty * price < min_usd:
        return None

    if max_qty and qty > max_qty:
        qty = max_qty

    return qty

