"""Utilities for risk analysis and position sizing."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from scalp.bot_config import CONFIG


def compute_position_size(
    equity_usdt: float,
    price: float,
    risk_pct: float,
    *,
    symbol: Optional[str] = None,
) -> int:
    """Return quantity to trade on the spot market.

    Parameters
    ----------
    equity_usdt:
        Total account equity in USDT.
    price:
        Current asset price in USDT.
    risk_pct:
        Fraction of equity to risk on the trade (e.g. ``0.01`` for 1%).

    The sizing logic is deliberately simple: the amount allocated to the trade
    is ``equity_usdt * risk_pct`` which is then divided by ``price`` to obtain
    the number of coins to buy or sell.  The result is floored to an integer to
    represent whole units of the base asset.
    """

    if equity_usdt <= 0 or price <= 0 or risk_pct <= 0:
        return 0

    notional = equity_usdt * float(risk_pct)
    qty = int(notional // price)
    return max(0, qty)


def analyse_risque(
    open_positions: List[Dict[str, Any]],
    equity_usdt: float,
    price: float,
    risk_pct: float,
    *,
    symbol: Optional[str] = None,
    side: str = "long",
    risk_level: int = 2,
) -> int:
    """Analyse le risque avant l'ouverture d'une position.

    The spot version only limits the number of concurrent positions for a
    given symbol and side.  ``risk_level`` controls how many simultaneous
    positions are allowed (1, 2 or 3).  When the limit is not exceeded the
    function returns the quantity suggested by :func:`compute_position_size`.
    Otherwise ``0`` is returned signalling that no trade should be opened.
    """

    symbol = symbol or CONFIG.get("SYMBOL")
    side = side.lower()

    max_positions_map = {1: 1, 2: 2, 3: 3}
    max_pos = max_positions_map.get(risk_level, max_positions_map[2])

    current = 0
    for pos in open_positions or []:
        if pos and pos.get("symbol") == symbol:
            if str(pos.get("side", "")).lower() == side:
                current += 1

    if current >= max_pos:
        return 0

    return compute_position_size(equity_usdt, price, risk_pct, symbol=symbol)


def trailing_stop(side: str, current_price: float, atr: float, sl: float, *, mult: float = 0.75) -> float:
    """Update a stop loss using a trailing ATR multiple."""

    if side.lower() == "long":
        new_sl = current_price - mult * atr
        return max(sl, new_sl)
    new_sl = current_price + mult * atr
    return min(sl, new_sl)


def break_even_stop(
    side: str,
    entry_price: float,
    current_price: float,
    atr: float,
    sl: float,
    *,
    mult: float = 1.0,
) -> float:
    """Move stop loss to break-even after a favourable move.

    Once price advances ``mult`` times the ``atr`` from ``entry_price`` the
    original stop loss ``sl`` is tightened to the entry.  This helps lock in
    profits while still giving the trade room to develop.
    """

    side = side.lower()
    if side == "long":
        if current_price - entry_price >= mult * atr:
            return max(sl, entry_price)
        return sl
    if side == "short":
        if entry_price - current_price >= mult * atr:
            return min(sl, entry_price)
        return sl
    raise ValueError("side must be 'long' or 'short'")


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


def marketable_limit_price(
    side: str,
    *,
    best_bid: float,
    best_ask: float,
    slippage: float = 0.001,
) -> float:
    """Return price for a marketable limit order with slippage cap.

    Parameters
    ----------
    side:
        ``"buy"`` or ``"sell"``.
    best_bid, best_ask:
        Current best bid and ask prices.
    slippage:
        Maximum relative slippage allowed (e.g. ``0.001`` = 0.1%).
    """

    if slippage < 0:
        raise ValueError("slippage must be non-negative")
    side = side.lower()
    if side == "buy":
        return best_ask * (1.0 + slippage)
    if side == "sell":
        return best_bid * (1.0 - slippage)
    raise ValueError("side must be 'buy' or 'sell'")
