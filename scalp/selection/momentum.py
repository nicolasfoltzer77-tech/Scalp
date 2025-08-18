"""Utilities to select pairs exhibiting strong momentum."""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from ..metrics import calc_atr


def ema(series: Sequence[float], window: int) -> List[float]:
    """Simple exponential moving average implementation."""

    if window <= 1 or not series:
        return list(series)
    k = 2.0 / (window + 1.0)
    out: List[float] = [float(series[0])]
    prev = out[0]
    for x in series[1:]:
        prev = float(x) * k + prev * (1.0 - k)
        out.append(prev)
    return out


def cross(last_fast: float, last_slow: float, prev_fast: float, prev_slow: float) -> int:
    """Return 1 if a bullish cross occurred, -1 for bearish, 0 otherwise."""

    if prev_fast <= prev_slow and last_fast > last_slow:
        return 1
    if prev_fast >= prev_slow and last_fast < last_slow:
        return -1
    return 0


def _quantile(values: Sequence[float], q: float) -> float:
    """Return the *q* quantile of *values* (0 <= q <= 1)."""

    if not values:
        return 0.0
    q = min(max(q, 0.0), 1.0)
    vals = sorted(values)
    idx = int((len(vals) - 1) * q)
    return vals[idx]


def select_active_pairs(
    client: Any,
    pairs: Sequence[Dict[str, Any]],
    *,
    interval: str = "Min5",
    ema_fast: int = 20,
    ema_slow: int = 50,
    atr_period: int = 14,
    atr_quantile: float = 0.5,
    top_n: int = 5,
) -> List[Dict[str, Any]]:
    """Return pairs with an EMA crossover and high ATR.

    Only pairs where ``EMA20`` crosses ``EMA50`` on the latest candle are kept.
    Among those candidates, the Average True Range is computed and only pairs
    whose ATR is above the provided quantile are returned.  The resulting
    dictionaries include an ``atr`` key for convenience.
    """

    candidates: List[Dict[str, Any]] = []
    atrs: List[float] = []

    for info in pairs:
        sym = info.get("symbol")
        if not sym:
            continue
        k = client.get_kline(sym, interval=interval)
        kdata = k.get("data") if isinstance(k, dict) else {}
        closes = kdata.get("close", [])
        highs = kdata.get("high", [])
        lows = kdata.get("low", [])
        if len(closes) < max(ema_slow, atr_period) + 2:
            continue
        efast = ema(closes, ema_fast)
        eslow = ema(closes, ema_slow)
        if cross(efast[-1], eslow[-1], efast[-2], eslow[-2]) == 0:
            continue
        atr_val = calc_atr(highs, lows, closes, atr_period)
        row = dict(info)
        row["atr"] = atr_val
        candidates.append(row)
        atrs.append(atr_val)

    if not candidates:
        return []

    threshold = _quantile(atrs, atr_quantile)
    selected = [row for row in candidates if row["atr"] >= threshold]
    selected.sort(key=lambda r: r["atr"], reverse=True)
    return selected[:top_n]


__all__ = ["select_active_pairs"]

