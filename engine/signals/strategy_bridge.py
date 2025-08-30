#!/usr/bin/env python3
from __future__ import annotations
from typing import Any, Dict, List, Optional
import inspect

# Imports tolérants (combine_signals peut ne pas exister suivant la branche)
from engine.strategies.runner import eval_strategy  # type: ignore
try:
    from engine.strategies.runner import combine_signals  # type: ignore
except Exception:  # pragma: no cover
    def combine_signals(items: List[Dict[str, Any]]) -> str:
        # Fallback très simple : si un BUY/SELL existe on le renvoie, sinon HOLD
        for k in ("BUY", "SELL"):
            if any((it.get("signal") or it.get("sig")) == k for it in items):
                return k
        return "HOLD"


def _call_eval_strategy(name: str,
                        symbol: str,
                        tf: Optional[str],
                        config: Optional[Dict[str, Any]],
                        ohlcv: Optional[List[List[float]]],
                        logger: Any) -> str:
    """
    Appelle eval_strategy avec robustesse selon sa signature réelle.
    Supporte: (name|strategy|strat) en kw, ou positionnel.
    """
    sig = inspect.signature(eval_strategy)
    params = sig.parameters

    # Mêmes noms
    if "name" in params:
        return eval_strategy(name=name, symbol=symbol, tf=tf, config=config, ohlcv=ohlcv, logger=logger)  # type: ignore
    if "strategy" in params:
        return eval_strategy(strategy=name, symbol=symbol, tf=tf, config=config, ohlcv=ohlcv, logger=logger)  # type: ignore
    if "strat" in params:
        return eval_strategy(strat=name, symbol=symbol, tf=tf, config=config, ohlcv=ohlcv, logger=logger)  # type: ignore

    # Positionnel (name, symbol, tf, config=None, ohlcv=None, logger=None)
    try:
        return eval_strategy(name, symbol, tf, config, ohlcv, logger)  # type: ignore
    except TypeError:
        # Dernier filet : on tente les 3 positionnels minimum
        return eval_strategy(name, symbol, tf)  # type: ignore


def evaluate_for(*,
                 symbol: str,
                 strategies: List[Dict[str, Any]] | List[str],
                 config: Optional[Dict[str, Any]] = None,
                 ohlcv: Optional[List[List[float]]] = None,
                 tf: Optional[str] = None,
                 logger: Any = None) -> Dict[str, Any]:
    """
    Évalue une liste de stratégies (format dict OU str) et renvoie:
    {
      "symbol": "...",
      "tf": "...",
      "combined": "BUY|SELL|HOLD",
      "items": [{"name": "...","tf": "...","signal": "..."}]
    }
    """
    items: List[Dict[str, Any]] = []

    for s in strategies or []:
        # Normalise entrée
        if isinstance(s, str):
            name = s
            stf = tf
        elif isinstance(s, dict):
            name = s.get("name") or s.get("id") or s.get("strategy") or ""
            stf = s.get("tf", tf)
        else:
            name = ""
            stf = tf

        if not name:
            if logger:
                logger.warning("strategy item sans nom: %r", s)
            continue

        try:
            sig = _call_eval_strategy(name=name,
                                      symbol=symbol,
                                      tf=stf,
                                      config=config,
                                      ohlcv=ohlcv,
                                      logger=logger)
        except Exception as e:  # On ne casse pas la boucle
            if logger:
                logger.exception("strategy '%s' failed on %s tf=%s", name, symbol, stf)
            sig = "HOLD"

        items.append({"name": name, "tf": stf or tf, "signal": sig})

    # Combine
    try:
        combined = combine_signals(items) if items else "HOLD"
    except Exception:
        combined = "HOLD"

    return {"symbol": symbol, "tf": tf, "combined": combined, "items": items}
