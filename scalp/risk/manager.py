# scalp/risk/manager.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class Caps:
    min_qty: float = 0.0           # quantité minimum
    min_notional: float = 0.0      # notionnel minimum (prix * qty)
    max_leverage: float = 20.0     # plafond de levier (indicatif, non utilisé ici v1)

def _get_caps(caps_by_symbol: Optional[Dict[str, Any]], symbol: str) -> Caps:
    if not caps_by_symbol:
        return Caps()
    c = caps_by_symbol.get(symbol, {})
    return Caps(
        min_qty=float(c.get("min_qty", 0.0) or 0.0),
        min_notional=float(c.get("min_notional", 0.0) or 0.0),
        max_leverage=float(c.get("max_leverage", 20.0) or 20.0),
    )

def compute_size(
    *,
    symbol: str,
    price: float,
    balance_cash: float,
    risk_pct: float = 0.5,
    caps_by_symbol: Optional[Dict[str, Any]] = None,
) -> float:
    """
    Calcule une taille 'qty' simple et robuste :
      qty = max(0, balance_cash * risk_pct / price)
    Puis applique des gardes (min_notional, min_qty).
    """
    price = max(1e-9, float(price))
    balance_cash = max(0.0, float(balance_cash))
    risk_pct = max(0.0, float(risk_pct))

    # sizing brut
    notionnel = balance_cash * risk_pct
    qty = notionnel / price

    # gardes
    caps = _get_caps(caps_by_symbol, symbol)
    # min_notional
    if caps.min_notional > 0 and (qty * price) < caps.min_notional:
        qty = caps.min_notional / price
    # min_qty
    if caps.min_qty > 0 and qty < caps.min_qty:
        qty = caps.min_qty

    # quantité non négative
    return max(0.0, qty)