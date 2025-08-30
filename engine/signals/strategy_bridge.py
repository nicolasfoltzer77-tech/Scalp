# /opt/scalp/engine/signals/strategy_bridge.py
# -*- coding: utf-8 -*-
"""
Pont d’intégration Bot <-> Strategies Runner
- charge les stratégies une fois
- expose compute(symbol, tf, ohlcv?) -> ("BUY"|"SELL"|"HOLD", details)
- log lisible : [strategies] SYMBOL@TF combined=... (sma=..., rsi=..., ema=...)
"""

from __future__ import annotations
from typing import Any, Dict, Optional

# 1) Runner de stratégies
from engine.strategies.runner import load_strategies, evaluate_for

# 2) Config stratégie optionnelle
def _load_strat_config() -> Dict[str, Any]:
    """
    Essaie de récupérer la section 'strategies' depuis la config centrale si elle existe.
    Fallback: dict vide.
    """
    try:
        # Si ton projet expose une CONFIG globale :
        #   from engine.config import CONFIG
        #   return CONFIG.get("strategies", {}) or {}
        # Sinon, tenter un loader s’il existe :
        from engine.config import load_config  # type: ignore
        cfg = load_config()
        return (cfg or {}).get("strategies", {}) or {}
    except Exception:
        return {}

_STRATS: Optional[Dict[str, Any]] = None
_STRAT_CFG: Dict[str, Any] = {}

def init(force: bool = False) -> None:
    """Charge les stratégies une fois (ou re-charge si force=True)."""
    global _STRATS, _STRAT_CFG
    if force or _STRATS is None:
        _STRATS = load_strategies()
        _STRAT_CFG = _load_strat_config()

def compute(symbol: str, tf: str, ohlcv: Optional[Any] = None, logger: Optional[Any] = None):
    """
    Retourne (combined, details) où:
        - combined ∈ {"BUY","SELL","HOLD"}
        - details  dict des sorties unitaires par stratégie
    ohlcv: dataframe/array optionnel si tu l’as déjà en main (sinon runner fait son propre load).
    """
    if _STRATS is None:
        init()

    # evaluate_for gère: strategies, config, ohlcv (si fourni)
    result = evaluate_for(
        symbol=symbol,
        tf=tf,
        strategies=_STRATS,           # type: ignore
        config=_STRAT_CFG,
        ohlcv=ohlcv
    )

    combined = result.get("combined", "HOLD")
    details = result.get("details", {})

    if logger:
        # Exemple: [strategies] ETHUSDT@1m combined=BUY (sma=BUY, rsi=HOLD, ema=BUY)
        parts = ", ".join(f"{k}={v}" for k, v in details.items())
        logger.info(f"[strategies] {symbol}@{tf} combined={combined} ({parts})")

    return combined, result
