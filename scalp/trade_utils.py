"""Utilities for risk analysis and position sizing."""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

from scalp.bot_config import CONFIG


def extract_contract_size(contract_detail: Dict[str, Any], symbol: Optional[str] = None) -> float:
    """Return the contract size for ``symbol`` from Bitget contract detail.

    Bitget's API sometimes exposes the contract unit as ``contractSize`` or
    ``sizeMultiplier`` depending on the endpoint or product type.  This helper
    normalises the two so the rest of the code base has a single source of
    truth for volume to notional conversions.
    """

    symbol = symbol or CONFIG.get("SYMBOL")
    data = contract_detail.get("data") if isinstance(contract_detail, dict) else None
    if isinstance(data, list):
        contract = next((c for c in data if c and c.get("symbol") == symbol), data[0] if data else {})
    else:
        contract = data or {}
    size = contract.get("contractSize") or contract.get("sizeMultiplier") or 1.0
    try:
        return float(size)
    except (TypeError, ValueError):
        return 1.0


def extract_available_balance(assets: Dict[str, Any], currency: str = "USDT") -> float:
    """Return available balance for ``currency`` from Bitget assets payload.

    The exchange may expose multiple fields depending on account mode and API
    version.  We iterate through the known keys, returning the first positive
    value encountered.  ``0.0`` is returned when no usable balance can be
    determined.  The helper only falls back to the more generic ``equity``
    fields when the granular balance keys are absent; if the exchange reports
    them with a ``0`` value we honour that and return ``0.0`` to avoid sizing
    orders against unavailable funds.
    """

    for row in assets.get("data", []):
        if row.get("currency") != currency:
            continue

        has_balance_field = False
        for key in (
            "available",
            "availableBalance",
            "availableMargin",
            "cashBalance",
        ):
            if key in row:
                has_balance_field = True
            val = row.get(key)
            if val is None:
                continue
            try:
                eq = float(val)
            except (TypeError, ValueError):
                continue
            if eq > 0:
                return eq

        if has_balance_field:
            return 0.0

        for key in ("equity", "usdtEquity"):
            val = row.get(key)
            if val is None:
                continue
            try:
                eq = float(val)
            except (TypeError, ValueError):
                continue
            if eq > 0:
                return eq
        break
    return 0.0


def compute_position_size(
    contract_detail: Dict[str, Any],
    equity_usdt: float,
    price: float,
    risk_pct: float,
    leverage: int,
    symbol: Optional[str] = None,
    available_usdt: Optional[float] = None,
) -> int:
    """Return contract volume to trade for the given risk parameters.

    The original implementation assumed ``price`` and contract metadata were
    always valid which could lead to divide-by-zero errors or negative volumes
    when the upstream API returned incomplete data.  To harden the sizing logic
    we now validate these inputs and simply return ``0`` whenever they are
    non‑positive.  The caller interprets a zero volume as a cue to skip the
    trade, keeping the bot running without raising exceptions.
    """

    symbol = symbol or CONFIG.get("SYMBOL")
    contracts = contract_detail.get("data") or []
    if not isinstance(contracts, list):
        contracts = [contracts]
    contract = next((c for c in contracts if c and c.get("symbol") == symbol), None)
    if contract is None:
        raise ValueError("Contract detail introuvable pour le symbole")

    contract_size = extract_contract_size(contract_detail, symbol)
    vol_unit = int(contract.get("volUnit", 1))
    min_vol = int(contract.get("minVol", 1))
    min_usdt = float(contract.get("minTradeUSDT", 5))

    if price <= 0 or contract_size <= 0 or vol_unit <= 0 or min_vol <= 0:
        return 0

    notional_target = equity_usdt * float(risk_pct) * float(leverage)
    if notional_target <= 0.0:
        return 0

    denom = price * contract_size
    if denom <= 0:
        return 0

    vol = notional_target / denom
    vol = int(math.floor(vol / vol_unit) * vol_unit)
    vol = max(min_vol, vol)
    notional = vol * denom
    if notional < min_usdt:
        return 0

    fee_rate = max(CONFIG.get("FEE_RATE", 0.0), 0.001)
    max_notional = equity_usdt / (1 / float(leverage) + fee_rate)
    max_vol = int(math.floor(max_notional / denom / vol_unit) * vol_unit)
    if max_vol < min_vol:
        return 0
    if vol > max_vol:
        vol = max_vol
        notional = vol * denom
        if notional < min_usdt:
            return 0

    if available_usdt is not None:
        cap = available_usdt / (1 / float(leverage) + fee_rate)
        cap_vol = int(math.floor(cap / denom / vol_unit) * vol_unit)
        if cap_vol < min_vol:
            return 0
        if vol > cap_vol:
            vol = cap_vol
            notional = vol * denom
            if notional < min_usdt:
                return 0

    return vol


def compute_pnl_usdt(
    contract_detail: Dict[str, Any],
    entry_price: float,
    exit_price: float,
    vol: float,
    side: int,
    symbol: Optional[str] = None,
) -> float:
    """Return PnL in USDT using contract size for ``vol`` contracts."""

    size = extract_contract_size(contract_detail, symbol)
    diff = (exit_price - entry_price) * (1 if side > 0 else -1)
    return diff * size * vol

def effective_leverage(
    entry_price: float,
    liquidation_price: float,
    position_margin: float,
    position_size: float,
) -> float:
    """Return the effective leverage of a futures position.

    ``effective_leverage`` is defined as the ratio between the position's
    notional value and the collateral backing it.  The collateral is primarily
    taken from ``position_margin`` but, when unavailable, it can be inferred
    from the distance to the liquidation price.

    The function is resilient to missing or non‑positive inputs and falls back
    to ``0.0`` whenever leverage cannot be determined.
    """

    try:
        entry = float(entry_price)
        liq = float(liquidation_price)
        margin = float(position_margin)
        size = float(position_size)
    except (TypeError, ValueError):
        return 0.0

    if entry <= 0 or size == 0:
        return 0.0

    notional = abs(size) * entry

    if margin <= 0:
        price_diff = abs(entry - liq)
        margin = price_diff * abs(size)

    if margin <= 0:
        return 0.0

    return notional / margin


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

    max_positions_map = {1: 1, 2: 3, 3: 5}
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
    """Return ``True`` when a position should be closed for lack of progress.

    Parameters
    ----------
    entry_time, now:
        Timestamps in **seconds**.  ``progress_min`` and ``timeout_min`` are
        expressed in minutes and converted to seconds inside the function so
        callers can provide human-friendly minute values.
    """

    # Convert the minute based thresholds to seconds for comparison with the
    # epoch based ``entry_time``/``now`` values.
    progress_sec = progress_min * 60.0
    timeout_sec = timeout_min * 60.0

    elapsed = now - entry_time
    if elapsed >= timeout_sec:
        return True
    if elapsed >= progress_sec:
        progress = (
            current_price - entry_price
            if side.lower() == "long"
            else entry_price - current_price
        )
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
