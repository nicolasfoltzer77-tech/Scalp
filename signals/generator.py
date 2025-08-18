from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from data.indicators import compute_all

__all__ = ["generate_signal"]


def _quality_from_score(score: float) -> str:
    if score >= 0.8:
        return "A"
    if score >= 0.5:
        return "B"
    return "C"


def generate_signal(
    df: pd.DataFrame,
    *,
    trend_tf: Optional[pd.DataFrame] = None,
    confirm_tf: Optional[pd.DataFrame] = None,
    atr_mult: float = 1.0,
    trailing: bool = False,
    **_: Any,
) -> Optional[Dict[str, Any]]:
    """Generate a trading signal with confluence scoring.

    Parameters
    ----------
    df: pd.DataFrame
        Primary timeframe OHLCV data.
    trend_tf: pd.DataFrame, optional
        Higher timeframe used for trend filtering.
    confirm_tf: pd.DataFrame, optional
        Lower timeframe used for confirmation.
    atr_mult: float, optional
        Multiplier applied to ATR for stop/target calculation.
    trailing: bool, optional
        When ``True`` include a ``trail`` distance (ATR * ``atr_mult``).

    Returns
    -------
    dict | None
        Dictionary describing the signal or ``None`` if no trade setup exists.
    """

    if df is None or len(df) < 2:
        return None

    df = compute_all(df)
    last = df.iloc[-1]

    conditions: List[bool] = []
    reasons: List[str] = []
    direction: Optional[str] = None

    # --- Basic trend via EMAs ----------------------------------------------
    if last["close"] > last["ema20"] > last["ema50"]:
        direction = "long"
        reasons.append("price_above_ema")
        conditions.append(True)
    elif last["close"] < last["ema20"] < last["ema50"]:
        direction = "short"
        reasons.append("price_below_ema")
        conditions.append(True)
    else:
        conditions.append(False)
        return None

    # --- RSI ---------------------------------------------------------------
    if direction == "long":
        cond = last["rsi"] > 55
        if cond:
            reasons.append("rsi_bullish")
        conditions.append(cond)
    else:
        cond = last["rsi"] < 45
        if cond:
            reasons.append("rsi_bearish")
        conditions.append(cond)

    # --- MACD --------------------------------------------------------------
    if direction == "long":
        cond = last["macd"] > last["macd_signal"]
        if cond:
            reasons.append("macd_bullish")
        conditions.append(cond)
    else:
        cond = last["macd"] < last["macd_signal"]
        if cond:
            reasons.append("macd_bearish")
        conditions.append(cond)

    # --- OBV momentum ------------------------------------------------------
    if len(df) >= 2:
        obv_up = df["obv"].iloc[-1] > df["obv"].iloc[-2]
        if obv_up:
            reasons.append("obv_trending")
        conditions.append(obv_up)

    # --- Trend timeframe filter -------------------------------------------
    if trend_tf is not None and len(trend_tf) >= 2:
        tdf = compute_all(trend_tf)
        ema50 = tdf["ema50"]
        slope = ema50.iloc[-1] - ema50.iloc[-2]
        if direction == "long":
            cond = slope > 0
            if cond:
                reasons.append("trend_up")
            conditions.append(cond)
        else:
            cond = slope < 0
            if cond:
                reasons.append("trend_down")
            conditions.append(cond)

    # --- Confirmation timeframe filter ------------------------------------
    if confirm_tf is not None and len(confirm_tf) > 0:
        cdf = compute_all(confirm_tf)
        rsi = cdf["rsi"].iloc[-1]
        if direction == "long":
            cond = rsi > 50
            if cond:
                reasons.append("confirm_rsi_bullish")
            conditions.append(cond)
        else:
            cond = rsi < 50
            if cond:
                reasons.append("confirm_rsi_bearish")
            conditions.append(cond)

    score = (
        sum(1 for c in conditions if c) / len(conditions) if conditions else 0.0
    )
    quality = _quality_from_score(score)

    atr = last.get("atr")
    if pd.isna(atr) or atr == 0:
        return None

    entry = float(last["close"])
    if direction == "long":
        sl = entry - atr * atr_mult
        tp = entry + atr * atr_mult * 2
    else:
        sl = entry + atr * atr_mult
        tp = entry - atr * atr_mult * 2

    result: Dict[str, Any] = {
        "direction": direction,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "score": round(score, 3),
        "reasons": reasons,
        "quality": quality,
    }

    if trailing:
        result["trail"] = atr * atr_mult

    return result
