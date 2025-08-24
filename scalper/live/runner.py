# scalper/live/runner.py
from __future__ import annotations
from typing import Dict, List, Any, Optional
from scalper.strategy.factory import resolve_signal_fn

class JobRunner:
    """
    Exécute un job (symbole, timeframe) :
      - reçoit des OHLCV déjà chargés
      - appelle la stratégie résolue
      - retourne le Signal (ou None)
    """
    def __init__(self, strategies_cfg: dict, equity: float, risk_pct: float) -> None:
        self.cfg = strategies_cfg
        self.equity = float(equity)
        self.risk = float(risk_pct)

    def run_once(
        self, *, symbol: str, timeframe: str,
        ohlcv: Dict[str, List[float]],
        ohlcv_1h: Optional[Dict[str, List[float]]] = None
    ):
        signal_fn = resolve_signal_fn(symbol, timeframe, self.cfg)
        return signal_fn(
            symbol=symbol, timeframe=timeframe, ohlcv=ohlcv,
            equity=self.equity, risk_pct=self.risk, ohlcv_1h=ohlcv_1h
        )