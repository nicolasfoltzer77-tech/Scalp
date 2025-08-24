from __future__ import annotations
import pandas as pd

def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=max(1,int(n)), adjust=False).mean()

def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = (high - low).abs().combine((high - prev_close).abs(), max).combine((low - prev_close).abs(), max)
    return tr.rolling(max(1,int(n))).mean()