# /opt/scalp/engine/signals/strategy_bridge.py
# Pont simple entre le pipeline et le moteur de stratégies.
# Il accepte tf (timeframe) en option pour rester compatible avec le pipeline.

from __future__ import annotations
from typing import Any, Dict, List, Optional

# On réutilise les helpers du runner de stratégies
from engine.strategies.runner import eval_strategy, combine_signals

Signal = str  # "BUY" | "SELL" | "HOLD"

def evaluate_for(
    *,
    symbol: str,
    strategies: List[Dict[str, Any]],
    config: Optional[Dict[str, Any]] = None,
    ohlcv: Optional[List[List[float]]] = None,
    tf: Optional[str] = None,
    logger: Any = None,
) -> Dict[str, Any]:
    """
    Évalue une liste de stratégies pour un symbole donné.

    Args:
        symbol: ex. "BTCUSDT"
        strategies: liste de stratégies (déjà chargées depuis le YAML)
        config: dict de config global (peut être None)
        ohlcv: données OHLCV déjà prêtes (ou None si chaque stratégie sait les charger)
        tf: timeframe courante (facultatif). Gardé pour compatibilité avec le pipeline.
        logger: logger optionnel

    Returns:
        dict avec:
            - symbol, tf
            - combined: signal agrégé
            - items: détail par stratégie [{"name","tf","signal"}...]
    """
    details: List[Dict[str, Any]] = []
    signals: List[Signal] = []

    # Sécurité: si pas de stratégies, on renvoie HOLD (ne bloque pas le pipeline)
    if not strategies:
        return {
            "symbol": symbol,
            "tf": tf,
            "combined": "HOLD",
            "items": [],
        }

    for strat in strategies:
        # Chaque stratégie peut définir son propre tf; on transmet quand même tf global
        # pour compatibilité (certaines strats l’ignorent).
        try:
            sig: Signal = eval_strategy(
                strat=strat,
                symbol=symbol,
                tf=tf,
                ohlcv=ohlcv,
                config=config,
                logger=logger,
            )
        except Exception as exc:  # on isole la casse d’une seule strat
            if logger:
                logger.exception("strategy '%s' failed on %s tf=%s", strat.get("name"), symbol, tf)
            # comportement fail-safe: on compte cette strat comme HOLD
            sig = "HOLD"

        details.append({
            "name": strat.get("name"),
            "tf": strat.get("tf", tf),
            "signal": sig,
        })
        signals.append(sig)

    combined: Signal = combine_signals(signals) if signals else "HOLD"

    return {
        "symbol": symbol,
        "tf": tf,
        "combined": combined,
        "items": details,
    }
