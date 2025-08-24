# engine/core/signals.py
from __future__ import annotations
import pandas as pd

def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def compute_signals(df: pd.DataFrame, params: dict[str, float]) -> pd.DataFrame:
    """
    Applique EMA crossover + ATR.
    Retourne DataFrame avec colonnes: ts, open, high, low, close, volume, ema_fast, ema_slow, atr, signal
    signal = +1 long / -1 short / 0 neutre
    """
    fast = int(params.get("ema_fast", 20))
    slow = int(params.get("ema_slow", 50))
    atr_period = int(params.get("atr_period", 14))

    out = df.copy()
    out["ema_fast"] = _ema(out["close"], fast)
    out["ema_slow"] = _ema(out["close"], slow)
    out["atr"] = _atr(out, atr_period)

    sig = 0
    signals = []
    for f, s in zip(out["ema_fast"], out["ema_slow"]):
        if pd.isna(f) or pd.isna(s):
            signals.append(0)
        elif f > s and sig <= 0:
            sig = 1
            signals.append(1)
        elif f < s and sig >= 0:
            sig = -1
            signals.append(-1)
        else:
            signals.append(sig)
    out["signal"] = signals
    return out