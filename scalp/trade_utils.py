"""Utilities for risk analysis and position sizing."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from scalp.bot_config import CONFIG


def compute_position_size(
    contract_detail: Dict[str, Any],
    equity_usdt: float,
    price: float,
    risk_pct: float,
    leverage: int,
    symbol: Optional[str] = None,
) -> int:
    """Return contract volume to trade for the given risk parameters."""
    symbol = symbol or CONFIG.get("SYMBOL")
    contracts = contract_detail.get("data") or []
    if not isinstance(contracts, list):
        contracts = [contracts]
    contract = next((c for c in contracts if c and c.get("symbol") == symbol), None)
    if contract is None:
        raise ValueError("Contract detail introuvable pour le symbole")

    contract_size = float(contract.get("contractSize", 0.0001))
    vol_unit = int(contract.get("volUnit", 1))
    min_vol = int(contract.get("minVol", 1))

    notional = equity_usdt * float(risk_pct) * float(leverage)
    if notional <= 0.0:
        return 0
    vol = notional / (price * contract_size)
    vol = int(math.floor(vol / vol_unit) * vol_unit)
    return max(min_vol, vol)


def analyse_risque(
    contract_detail: Dict[str, Any],
    open_positions: List[Dict[str, Any]],
    equity_usdt: float,
    price: float,
    risk_pct: float,
    base_leverage: int,
    symbol: Optional[str] = None,
    side: str = "long",
    risk_level: int = 2,
) -> Tuple[int, int]:
    """Analyse le risque avant l'ouverture d'une position."""
    symbol = symbol or CONFIG.get("SYMBOL")
    side = side.lower()

    max_positions_map = {1: 1, 2: 2, 3: 3}
    leverage_map = {1: max(1, base_leverage // 2), 2: base_leverage, 3: base_leverage * 2}

    max_pos = max_positions_map.get(risk_level, max_positions_map[2])
    leverage = leverage_map.get(risk_level, base_leverage)

    current = 0
    for pos in open_positions or []:
        if pos and pos.get("symbol") == symbol:
            if str(pos.get("side", "")).lower() == side:
                current += 1

    if current >= max_pos:
        return 0, leverage

    vol = compute_position_size(
        contract_detail,
        equity_usdt=equity_usdt,
        price=price,
        risk_pct=risk_pct,
        leverage=leverage,
        symbol=symbol,
    )
    return vol, leverage


def trailing_stop(side: str, current_price: float, atr: float, sl: float, *, mult: float = 0.75) -> float:
    """Update a stop loss using a trailing ATR multiple."""

    if side.lower() == "long":
        new_sl = current_price - mult * atr
        return max(sl, new_sl)
    new_sl = current_price + mult * atr
    return min(sl, new_sl)


def should_scale_in(
    entry_price: float,
    current_price: float,
    last_entry: float,
    atr: float,
    side: str,
    *,
    distance_mult: float = 0.5,
) -> bool:
    """Return ``True`` when price moved sufficiently to add to the position."""

    if side.lower() == "long":
        target = last_entry + distance_mult * atr
        return current_price >= target
    target = last_entry - distance_mult * atr
    return current_price <= target


def timeout_exit(
    entry_time: float,
    now: float,
    entry_price: float,
    current_price: float,
    side: str,
    *,
    progress_min: float = 15.0,
    timeout_min: float = 30.0,
) -> bool:
    """Return ``True`` when a position should be closed for lack of progress."""

    elapsed = now - entry_time
    if elapsed >= timeout_min:
        return True
    if elapsed >= progress_min:
        progress = (current_price - entry_price) if side.lower() == "long" else (entry_price - current_price)
        return progress <= 0
    return False
