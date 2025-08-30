# /opt/scalp/engine/signals/strategy_bridge.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Any, Dict, Optional

from engine.strategies.runner import load_strategies, evaluate_for

def _load_strat_config() -> Dict[str, Any]:
    try:
        from engine.config import load_config  # optionnel si présent
        cfg = load_config()
        return (cfg or {}).get("strategies", {}) or {}
    except Exception:
        return {}

_STRATS: Optional[Dict[str, Any]] = None
_CFG: Dict[str, Any] = {}

def init(force: bool = False) -> None:
    global _STRATS, _CFG
    if force or _STRATS is None:
        _STRATS = load_strategies()
        _CFG = _load_strat_config()

def compute(symbol: str, tf: str, ohlcv: Optional[Any] = None, logger: Optional[Any] = None):
    if _STRATS is None:
        init()
    result = evaluate_for(symbol=symbol, tf=tf, strategies=_STRATS, config=_CFG, ohlcv=ohlcv)
    combined = result.get("combined", "HOLD")
    details = result.get("details", {})
    if logger:
        parts = ", ".join(f"{k}={v}" for k, v in details.items())
        logger.info(f"[strategies] {symbol}@{tf} combined={combined} ({parts})")
    return combined, result
