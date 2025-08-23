# scalper/trade_utils.py
from __future__ import annotations

from typing import Optional


def compute_position_size(
    equity: float,
    price: float,
    risk_pct: float,
    *,
    symbol: Optional[str] = None,
    min_qty: float = 0.0,
    max_leverage: float = 1.0,
) -> float:
    """
    Sizing simple: position notionnelle = equity * risk_pct * max_leverage
    qty = notionnel / price
    - min_qty : borne basse éventuelle (0 pour ignorer)
    - max_leverage : si tu veux simuler un levier (1 par défaut)
    """
    equity = float(max(0.0, equity))
    price = float(max(1e-12, price))
    risk_pct = float(max(0.0, risk_pct))
    notionnel = equity * risk_pct * max_leverage
    qty = notionnel / price
    if min_qty > 0 and qty < min_qty:
        return 0.0
    return float(qty)