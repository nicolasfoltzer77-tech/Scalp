"""Utilities for scanning tradable pairs on the exchange."""

from __future__ import annotations

from typing import Any, Dict, List


def scan_pairs(
    client: Any,
    *,
    volume_min: float = 5_000_000,
    max_spread_bps: float = 5.0,
    min_hourly_vol: float = 0.0,
    top_n: int = 20,
) -> List[Dict[str, Any]]:
    """Return pairs satisfying basic liquidity and volatility filters.

    Parameters
    ----------
    client: Any
        Client instance exposing ``get_ticker`` and ``get_kline`` methods.
    volume_min: float, optional
        Minimum 24h volume required to keep a pair.
    max_spread_bps: float, optional
        Maximum allowed bid/ask spread expressed in basis points.
    min_hourly_vol: float, optional
        Minimum volatility over the last hour expressed as ``(high - low) /
        close``.  When set to ``0`` the filter is disabled.
    top_n: int, optional
        Limit the number of returned pairs.
    """

    tick = client.get_ticker()
    data = tick.get("data") if isinstance(tick, dict) else []
    if not isinstance(data, list):
        data = [data]

    eligible: List[Dict[str, Any]] = []

    for row in data:
        sym = row.get("symbol")
        if not sym:
            continue
        try:
            vol = float(row.get("volume", 0))
            bid = float(row.get("bidPrice", 0))
            ask = float(row.get("askPrice", 0))
        except (TypeError, ValueError):
            continue
        if vol < volume_min or bid <= 0 or ask <= 0:
            continue
        spread_bps = (ask - bid) / ((ask + bid) / 2.0) * 10_000
        if spread_bps >= max_spread_bps:
            continue

        if min_hourly_vol > 0:
            k = client.get_kline(sym, interval="Min60")
            kdata = k.get("data") if isinstance(k, dict) else {}
            highs = kdata.get("high", [])
            lows = kdata.get("low", [])
            closes = kdata.get("close", [])
            if not highs or not lows or not closes:
                continue
            try:
                h = float(highs[-1])
                l = float(lows[-1])
                c = float(closes[-1])
            except (TypeError, ValueError):
                continue
            hourly_vol = (h - l) / c if c else 0.0
            if hourly_vol < min_hourly_vol:
                continue

        eligible.append(row)

    eligible.sort(key=lambda r: float(r.get("volume", 0)), reverse=True)
    return eligible[:top_n]


__all__ = ["scan_pairs"]

