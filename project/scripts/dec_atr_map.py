#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DEC — ATR MAP (FAST + SLOW MERGE)
"""

from dec_atr_fast import load_atr_fast_map
from dec_atr_slow import load_atr_slow_map

def load_atr_map():
    fast = load_atr_fast_map()
    slow = load_atr_slow_map()

    out = {}

    keys = set(fast.keys()) | set(slow.keys())
    for instId in keys:
        row = {}
        if instId in fast:
            row.update(dict(fast[instId]))
        if instId in slow:
            row.update(dict(slow[instId]))
        out[instId] = row

    return out

