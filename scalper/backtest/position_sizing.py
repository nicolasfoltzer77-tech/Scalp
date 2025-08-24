# scalper/backtest/position_sizing.py
from __future__ import annotations
from scalper.core.signal import Signal

def position_size_from_signal(equity: float, sig: Signal, risk_pct: float) -> float:
    """
    Taille: (equity * risk_pct) / distance (entry↔SL)
    Hypothèse: prix coté en devise de base (ex: USDT).
    Retourne une QUANTITÉ (unités de la crypto).
    """
    risk = max(1e-12, abs(sig.entry - sig.sl))
    cash_at_risk = max(0.0, equity) * max(0.0, risk_pct)
    qty = cash_at_risk / risk
    return max(0.0, qty)

def fees_cost(notional: float, bps: float) -> float:
    return abs(notional) * (bps / 10000.0)