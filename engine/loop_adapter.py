# engine/loop_adapter.py
from __future__ import annotations
from typing import Dict, List, Optional
from engine.hook import on_tick

def process_selection_tick(
    *,
    symbol: str,
    last_price: float,
    atr: float,
    allow_long: bool,
    allow_short: bool,
    selection_metrics: Dict,
    bars_1s: Optional[List[dict]] = None,
    notes: str = "live-feed"
):
    """
    Appelle ce wrapper depuis TA boucle existante.
    - selection_metrics: dict de tes features (ema_fast/slow/long, macd_hist, rsi, adx, obv_slope, vol_atr_pct, etc.)
    - bars_1s: liste d'OHLCV 1s récents (optionnel, recommandé si accessible)
    """
    return on_tick(
        symbol=symbol,
        price=last_price,
        atr=atr,
        allow_long=allow_long,
        allow_short=allow_short,
        selection_metrics=selection_metrics,
        bars_1s=bars_1s,
        notes=notes
    )
