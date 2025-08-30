from __future__ import annotations
from typing import Any, Dict, List, Optional
from engine.strategies.runner import eval_strategy

Signal = str  # "BUY" | "SELL" | "HOLD"

def combine_signals(signals: List[Signal]) -> Signal:
    """Combine plusieurs signaux en un seul."""
    if not signals:
        return "HOLD"
    if "BUY" in signals and "SELL" not in signals:
        return "BUY"
    if "SELL" in signals and "BUY" not in signals:
        return "SELL"
    return "HOLD"

def evaluate_for(
    *,
    symbol: str,
    strategies: List[Dict[str, Any]],
    config: Optional[Dict[str, Any]] = None,
    ohlcv: Optional[List[List[float]]] = None,
    tf: Optional[str] = None,
    logger: Any = None,
) -> Dict[str, Any]:
    details: List[Dict[str, Any]] = []
    signals: List[Signal] = []
    if not strategies:
        return {"symbol": symbol, "tf": tf, "combined": "HOLD", "items": []}
    for strat in strategies:
        try:
            sig: Signal = eval_strategy(
                strat=strat, symbol=symbol, tf=tf,
                ohlcv=ohlcv, config=config, logger=logger,
            )
        except Exception:
            if logger:
                logger.exception("strategy '%s' failed on %s tf=%s", strat.get("name"), symbol, tf)
            sig = "HOLD"
        details.append({"name": strat.get("name"), "tf": strat.get("tf", tf), "signal": sig})
        signals.append(sig)
    combined: Signal = combine_signals(signals) if signals else "HOLD"
    return {"symbol": symbol, "tf": tf, "combined": combined, "items": details}
