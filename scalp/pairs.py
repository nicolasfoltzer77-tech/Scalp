"""Utilities to select trading pairs and detect signals."""
from __future__ import annotations

from typing import Any, Dict, List, Callable

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
    top_n: int = 20,
) -> List[Dict[str, Any]]:
    """Filter pairs by volume and spread."""
    pairs = get_trade_pairs(client)
    eligible: List[Dict[str, Any]] = []

    for info in pairs:
        sym = info.get("symbol")
        if not sym:
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


def send_selected_pairs(
    client: Any,
    top_n: int = 20,
    *,
    select_fn: Callable[[Any, int], List[Dict[str, Any]]] = select_top_pairs,
    notify_fn: Callable[[str, Optional[Dict[str, Any]]], None] = notify,
) -> None:
    """Fetch top pairs, drop USD duplicates and notify their list.

    Returns the payload sent to ``notify_fn`` for convenience.
    """

    def split_symbol(sym: str) -> tuple[str, str]:
        if "_" in sym:
            base, quote = sym.split("_", 1)
        elif sym.endswith("USDT"):
            base, quote = sym[:-4], "USDT"
        elif sym.endswith("USD"):
            base, quote = sym[:-3], "USD"
        else:
            base, quote = sym, ""
        return base, quote

    pairs = select_fn(client, top_n=top_n * 3)
    by_base: Dict[str, Dict[str, Any]] = {}
    for info in pairs:
        sym = info.get("symbol")
        if not sym:
            continue
        base, quote = split_symbol(sym)
        existing = by_base.get(base)
        if existing is None or (existing["quote"] != "USDT" and quote == "USDT"):
            by_base[base] = {"data": info, "quote": quote}

    unique = sorted(
        (v["data"] for v in by_base.values()),
        key=lambda row: float(row.get("volume", 0)),
        reverse=True,
    )
    symbols: list[str] = []
    for row in unique[:top_n]:
        sym = row.get("symbol")
        if not sym:
            continue
        base, _ = split_symbol(sym)
        symbols.append(base)
    if symbols:
        n = len(symbols)
        third = max(n // 3, 1)
        green = symbols[:third]
        orange = symbols[third : 2 * third]
        red = symbols[2 * third :]
        payload: Dict[str, str] = {}
        if green:
            payload["green"] = ", ".join(green)
        if orange:
            payload["orange"] = ", ".join(orange)
        if red:
            payload["red"] = ", ".join(red)
        notify_fn("pair_list", payload)
        return payload
    return {}


def heat_score(volatility: float, volume: float, news: bool = False) -> float:
    """Return a heat score combining volatility, volume and a news flag."""
    mult = 2.0 if news else 1.0
    return volatility * volume * mult


def select_top_heat_pairs(
    pairs: List[Dict[str, Any]], *, top_n: int = 3
) -> List[Dict[str, Any]]:
    """Return ``top_n`` pairs ranked by ``heat_score``."""

    scored: List[Dict[str, Any]] = []
    for info in pairs:
        try:
            vol = float(info.get("volatility", 0))
            volume = float(info.get("volume", 0))
        except (TypeError, ValueError):
            continue
        score = heat_score(vol, volume, bool(info.get("news")))
        row = dict(info)
        row["heat_score"] = score
        scored.append(row)

    scored.sort(key=lambda r: r["heat_score"], reverse=True)
    return scored[:top_n]


def decorrelate_pairs(
    pairs: List[Dict[str, Any]],
    corr: Dict[str, Dict[str, float]],
    *,
    threshold: float = 0.8,
    top_n: int = 3,
) -> List[Dict[str, Any]]:
    """Return top pairs while avoiding highly correlated symbols.

    ``corr`` is a mapping of pair symbol to correlation with other symbols.  Two
    pairs are considered too correlated when the absolute value of the
    correlation exceeds ``threshold``.
    """

    selected: List[Dict[str, Any]] = []
    for info in select_top_heat_pairs(pairs, top_n=len(pairs)):
        sym = info.get("symbol")
        if not sym:
            continue
        if all(abs(corr.get(sym, {}).get(p["symbol"], 0.0)) < threshold for p in selected):
            selected.append(info)
        if len(selected) >= top_n:
            break
    return selected
