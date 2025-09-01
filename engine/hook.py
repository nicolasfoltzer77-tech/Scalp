# engine/hook.py
from __future__ import annotations
from typing import Optional, Dict, List
from services.orchestrator import Orchestrator
from engine.scorer import Scorer

_ORCH = Orchestrator()
_SCORER = Scorer()

def on_tick(
    *,
    symbol: str,
    price: float,
    atr: float,
    allow_long: bool,
    allow_short: bool,
    score: Optional[float] = None,
    selection_metrics: Optional[Dict] = None,
    bars_1s: Optional[List[dict]] = None,
    quality: Optional[Dict[str, float]] = None,
    notes: Optional[str] = None,
):
    # si aucun score fourni, on le dérive des métriques de sélection (+affinage 1s)
    if score is None:
        base = _SCORER.score_from_selection(selection_metrics or {})
        score = _SCORER.refine_with_1s(base, bars_1s)
    qual = dict(quality or {})
    if selection_metrics:
        for k in ("rsi","adx","macd_hist","obv_slope"):
            if k in selection_metrics:
                try: qual[k] = float(selection_metrics[k])
                except Exception: pass

    return _ORCH.process_tick(
        symbol=symbol, price=price, atr=atr, score=score,
        allow_long=allow_long, allow_short=allow_short,
        quality_components=qual, notes=notes, open_if_signal=True
    )
