"""Utilities to select trading pairs and detect signals."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from scalp.bot_config import CONFIG
from scalp.strategy import ema as default_ema, cross as default_cross
from scalp.notifier import notify


def get_trade_pairs(client: Any) -> List[Dict[str, Any]]:
    """Return all trading pairs using the client's ``get_ticker`` method."""
    tick = client.get_ticker()
    data = tick.get("data") if isinstance(tick, dict) else []
    if not data:
        return []
    return data if isinstance(data, list) else [data]


def filter_trade_pairs(
    client: Any,
    *,
    volume_min: float = 5_000_000,
    max_spread_bps: float = 5.0,
    zero_fee_pairs: Optional[List[str]] = None,
    top_n: int = 20,
) -> List[Dict[str, Any]]:
    """Filter pairs by volume, spread and zero fees."""
    pairs = get_trade_pairs(client)
    zero_fee = set(zero_fee_pairs or CONFIG.get("ZERO_FEE_PAIRS", []))
    eligible: List[Dict[str, Any]] = []

    for info in pairs:
        sym = info.get("symbol")
        if not sym or sym not in zero_fee:
            continue
        try:
            vol = float(info.get("volume", 0))
        except (TypeError, ValueError):
            continue
        if vol < volume_min:
            continue
        try:
            bid = float(info.get("bidPrice", 0))
            ask = float(info.get("askPrice", 0))
        except (TypeError, ValueError):
            continue
        if bid <= 0 or ask <= 0:
            continue
        spread_bps = (ask - bid) / ((ask + bid) / 2) * 10_000
        if spread_bps >= max_spread_bps:
            continue
        eligible.append(info)

    eligible.sort(key=lambda row: float(row.get("volume", 0)), reverse=True)
    return eligible[:top_n]


def select_top_pairs(client: Any, top_n: int = 10, key: str = "volume") -> List[Dict[str, Any]]:
    """Return ``top_n`` pairs sorted by ``key``."""
    pairs = get_trade_pairs(client)

    def volume(row: Dict[str, Any]) -> float:
        try:
            return float(row.get(key, 0))
        except (TypeError, ValueError):
            return 0.0

    pairs.sort(key=volume, reverse=True)
    return pairs[:top_n]


def find_trade_positions(
    client: Any,
    pairs: List[Dict[str, Any]],
    *,
    interval: str = "Min1",
    ema_fast_n: Optional[int] = None,
    ema_slow_n: Optional[int] = None,
    ema_func=default_ema,
    cross_func=default_cross,
) -> List[Dict[str, Any]]:
    """Apply EMA crossover strategy on ``pairs`` and return signals."""
    ema_fast_n = ema_fast_n or CONFIG.get("EMA_FAST", 9)
    ema_slow_n = ema_slow_n or CONFIG.get("EMA_SLOW", 21)
    results: List[Dict[str, Any]] = []

    for info in pairs:
        symbol = info.get("symbol")
        if not symbol:
            continue
        k = client.get_kline(symbol, interval=interval)
        closes = k.get("data", {}).get("close", []) if isinstance(k, dict) else []
        if len(closes) < max(ema_fast_n, ema_slow_n) + 2:
            continue
        efull = ema_func(closes, ema_fast_n)
        eslow = ema_func(closes, ema_slow_n)
        signal = cross_func(efull[-1], eslow[-1], efull[-2], eslow[-2])
        if signal == 1:
            results.append({"symbol": symbol, "signal": "long", "price": float(info.get("lastPrice", 0.0))})
        elif signal == -1:
            results.append({"symbol": symbol, "signal": "short", "price": float(info.get("lastPrice", 0.0))})
    return results


def send_selected_pairs(client: Any, top_n: int = 20) -> None:
    """Fetch top pairs and notify their list."""
    pairs = select_top_pairs(client, top_n=top_n)
    symbols = [p.get("symbol") for p in pairs if p.get("symbol")]
    if symbols:
        notify("pair_list", {"pairs": ", ".join(symbols)})
