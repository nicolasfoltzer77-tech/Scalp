# /opt/scalp/engine/risk/limits.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import os

def env_float(name: str, default: float) -> float:
    try: return float(os.environ.get(name, default))
    except Exception: return float(default)

MAX_SIZE_USDT   = env_float("MAX_SIZE_USDT",   50)
MAX_LEVERAGE    = env_float("MAX_LEVERAGE",     2)
SPREAD_BPS      = env_float("SPREAD_SLIPPAGE_BPS", 3)

def allowed_size_usdt(symbol: str) -> float:
    # hook: tu peux affiner par symbole ici
    return MAX_SIZE_USDT

def should_open(symbol: str, side: str, price: float|None) -> bool:
    # hook: empêcher sur volatilité extrême, PnL, etc.
    return True

def choose_action_from_signal(sig: str) -> str:
    if sig == "BUY":  return "OPEN_LONG"
    if sig == "SELL": return "OPEN_SHORT"
    return "HOLD"
