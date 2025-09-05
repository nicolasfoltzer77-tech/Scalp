#!/usr/bin/env python3
from __future__ import annotations
from typing import Any, Dict, List, Optional
import inspect

# Import du runner
from engine.strategies.runner import eval_strategy  # type: ignore
try:
    from engine.strategies.runner import combine_signals  # type: ignore
except Exception:  # pragma: no cover
    def combine_signals(items: List[Dict[str, Any]]) -> str:
        # Fallback simple
        for k in ("BUY", "SELL"):
            if any((it.get("signal") or it.get("sig")) == k for it in items):
                return k
        return "HOLD"


def _mk_ctx(symbol: str,
            tf: Optional[str],
            config: Optional[Dict[str, Any]],
            ohlcv: Optional[List[List[float]]],
            logger: Any) -> Dict[str, Any]:
    return {"symbol": symbol, "tf": tf, "config": config, "ohlcv": ohlcv, "logger": logger}


def _call_eval_strategy(name: str,
                        symbol: str,
                        tf: Optional[str],
                        config: Optional[Dict[str, Any]],
                        ohlcv: Optional[List[List[float]]],
                        logger: Any) -> str:
    """
    Appelle eval_strategy en s'adaptant à sa signature:
    - param kw: name / strategy / strat
    - param kw: ctx / context / env
    - 2 positionnels (name, ctx) ou (strategy, ctx)
    - sinon, on tente une combinaison raisonnable puis on fallback.
    """
    sig = inspect.signature(eval_strategy)
    params = sig.parameters
    ctx = _mk_ctx(symbol, tf, config, ohlcv, logger)

    # Prépare des kwargs compatibles
    kwargs: Dict[str, Any] = {}
    for key in ("symbol", "tf", "config", "ohlcv", "logger"):
        if key in params:
            kwargs[key] = ctx[key]

    # Nom de stratégie par kw si disponible
    if "name" in params:
        return eval_strategy(name=name, **kwargs)  # type: ignore
    if "strategy" in params:
        return eval_strategy(strategy=name, **kwargs)  # type: ignore
    if "strat" in params:
        return eval_strategy(strat=name, **kwargs)  # type: ignore

    # Contexte par kw si demandé
    for ckey in ("ctx", "context", "env"):
        if ckey in params:
            return eval_strategy(**{ckey: ctx, **kwargs})  # type: ignore

    # Analyse des positionnels requis (hors *args/**kwargs et hors self)
    required_pos = [
        p for p in params.values()
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY,
                      inspect.Parameter.POSITIONAL_OR_KEYWORD)
        and p.default is inspect._empty and p.name != "self"
    ]

    # Cas courant rencontré: 2 positionnels -> (name, ctx)
    if len(required_pos) == 2:
        try:
            return eval_strategy(name, ctx)  # type: ignore
        except TypeError:
            # Tentative alternative: (ctx, name)
            try:
                return eval_strategy(ctx, name)  # type: ignore
            except TypeError:
                pass

    # 1 positionnel requis -> essaye name, sinon ctx
    if len(required_pos) == 1:
        try:
            return eval_strategy(name, **kwargs)  # type: ignore
        except TypeError:
            return eval_strategy(ctx, **kwargs)  # type: ignore

    # Dernières tentatives "raisonnables"
    for attempt in (
        lambda: eval_strategy(name, symbol, tf, config, ohlcv, logger),  # type: ignore
        lambda: eval_strategy(name, symbol, tf),                         # type: ignore
        lambda: eval_strategy(name),                                     # type: ignore
        lambda: eval_strategy(ctx),                                      # type: ignore
    ):
        try:
            return attempt()
        except TypeError:
            continue

    # Fallback final
    return "HOLD"


def evaluate_for(*,
                 symbol: str,
                 strategies: List[Dict[str, Any]] | List[str],
                 config: Optional[Dict[str, Any]] = None,
                 ohlcv: Optional[List[List[float]]] = None,
                 tf: Optional[str] = None,
                 logger: Any = None) -> Dict[str, Any]:
    """
    Évalue une liste de stratégies (str ou dict) et renvoie un dict standardisé.
    """
    items: List[Dict[str, Any]] = []

    for s in strategies or []:
        # Normalisation input
        if isinstance(s, str):
            name = s
            stf = tf
        elif isinstance(s, dict):
            name = s.get("name") or s.get("id") or s.get("strategy") or s.get("strat") or ""
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
        except Exception:
            if logger:
                logger.exception("strategy '%s' failed on %s tf=%s", name, symbol, stf)
            sig = "HOLD"

        items.append({"name": name, "tf": stf or tf, "signal": sig})

    try:
        combined = combine_signals(items) if items else "HOLD"
    except Exception:
        combined = "HOLD"

    return {"symbol": symbol, "tf": tf, "combined": combined, "items": items}
