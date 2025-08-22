"""Utilities for risk analysis and position sizing."""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

from scalp.bot_config import CONFIG


def get_contract_size(contract_detail: Dict[str, Any], symbol: Optional[str] = None) -> float:
    """Return the contract size for ``symbol``.

    Bitget may expose the contract unit as ``contractSize`` or
    ``sizeMultiplier`` depending on the endpoint.  This helper normalises the
    two so the rest of the code base has a single source of truth for
    conversions between contract volume and notional value.
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


# Backwards compatibility: old name used internally/tests
extract_contract_size = get_contract_size


def notional(price: float, vol: float, contract_size: float) -> float:
    """Return the notional value in USDT for ``vol`` contracts."""

    return float(price) * float(vol) * float(contract_size)


def required_margin(
    notion: float,
    lev: float,
    fee_rate: float,
    buffer: float = 0.03,
) -> float:
    """Return estimated required margin including fees and buffer.

    The margin is the sum of the collateral required by the leverage and the
    estimated taker fees for both sides of the trade.  ``buffer`` adds an extra
    safety margin to account for slight price movements between order placement
    and execution.
    """

    lev = max(float(lev), 1.0)
    fee = float(fee_rate)
    return (notion / lev + fee * notion) * (1.0 + buffer)


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


def compute_execution_metrics(
    fills: List[Dict[str, Any]], *, contract_size: float = 1.0
) -> Tuple[float, float, float]:
    """Aggregate Bitget fills into execution metrics.

    Parameters
    ----------
    fills:
        Sequence of fill dictionaries containing price and quantity.  The
        helper accepts the common Bitget keys ``fillPrice``/``price`` and
        ``fillQty``/``size``/``vol`` for the executed quantity.  Unknown or
        malformed entries are ignored.
    contract_size:
        Multiplier to convert contract volume into notional value.

    Returns
    -------
    tuple
        ``(exec_qty, exec_notional, avg_exec_price)`` where quantities are in
        contract units and notional is expressed in quote currency.
    """

    exec_qty = 0.0
    exec_notional = 0.0
    for f in fills:
        price = f.get("fillPrice") or f.get("price")
        qty = f.get("fillQty") or f.get("size") or f.get("vol") or f.get("qty")
        try:
            price_f = float(price)
            qty_f = float(qty)
        except (TypeError, ValueError):
            continue
        exec_qty += qty_f
        exec_notional += price_f * qty_f * contract_size

    avg_price = exec_notional / (exec_qty * contract_size) if exec_qty else 0.0
    return exec_qty, exec_notional, avg_price


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

    contract_size = get_contract_size(contract_detail, symbol)
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

    size = get_contract_size(contract_detail, symbol)
    diff = (exit_price - entry_price) * (1 if side > 0 else -1)
    return diff * size * vol


def compute_pnl_with_fees(
    contract_detail: Dict[str, Any],
    entry_price: float,
    exit_price: float,
    vol: float,
    side: int,
    leverage: float,
    fee_rate: float,
    symbol: Optional[str] = None,
) -> Tuple[float, float]:
    """Return net PnL in USDT and percentage on margin.

    ``side`` should be ``1`` for long positions and ``-1`` for shorts.
    """

    cs = get_contract_size(contract_detail, symbol)
    n_entry = notional(entry_price, vol, cs)
    n_exit = notional(exit_price, vol, cs)
    gross = (exit_price - entry_price) * vol * cs * (1 if side > 0 else -1)
    fees = fee_rate * (n_entry + n_exit)
    pnl = gross - fees
    margin = n_entry / max(float(leverage), 1.0)
    pct = 0.0 if margin == 0 else pnl / margin * 100.0
    return pnl, pct

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
