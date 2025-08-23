# scalp/risk/manager.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class Caps:
    min_qty: float = 0.0
    min_notional: float = 0.0
    max_leverage: float = 20.0

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
    """Sizing robuste avec gardes min_notional / min_qty."""
    price = max(1e-9, float(price))
    balance_cash = max(0.0, float(balance_cash))
    risk_pct = max(0.0, float(risk_pct))

    notionnel = balance_cash * risk_pct
    qty = notionnel / price

    caps = _get_caps(caps_by_symbol, symbol)
    if caps.min_notional > 0 and (qty * price) < caps.min_notional:
        qty = caps.min_notional / price
    if caps.min_qty > 0 and qty < caps.min_qty:
        qty = caps.min_qty
    return max(0.0, qty)

# --- Shims pour compatibilité ancienne API -----------------------------------

def calc_position_size(symbol: str, price: float, balance_cash: float,
                       risk_pct: float = 0.5,
                       caps_by_symbol: Optional[Dict[str, Any]] = None) -> float:
    """Alias legacy → compute_size."""
    return compute_size(
        symbol=symbol, price=price, balance_cash=balance_cash,
        risk_pct=risk_pct, caps_by_symbol=caps_by_symbol
    )

class RiskManager:
    """
    Shim minimal compatible avec l'ancien code:
      rm = RiskManager(risk_pct=0.5, caps_by_symbol={...})
      qty = rm.size(symbol, price, balance_cash)
    """
    def __init__(self, risk_pct: float = 0.5, caps_by_symbol: Optional[Dict[str, Any]] = None):
        self.risk_pct = float(risk_pct)
        self.caps_by_symbol = caps_by_symbol or {}

    def size(self, symbol: str, price: float, balance_cash: float) -> float:
        return compute_size(
            symbol=symbol, price=price, balance_cash=balance_cash,
            risk_pct=self.risk_pct, caps_by_symbol=self.caps_by_symbol
        )