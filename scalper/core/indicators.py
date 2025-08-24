# scalper/core/indicators.py
from __future__ import annotations
from typing import Sequence, Tuple, List

def _to_list(x: Sequence[float]) -> List[float]:
    return list(map(float, x))

def ema(series: Sequence[float], period: int) -> List[float]:
    s = _to_list(series)
    if period <= 1 or len(s) == 0:
        return s[:]
    k = 2.0 / (period + 1.0)
    out = [s[0]]
    for i in range(1, len(s)):
        out.append(s[i] * k + out[-1] * (1.0 - k))
    return out

def sma(series: Sequence[float], period: int) -> List[float]:
    s = _to_list(series)
    out: List[float] = []
    acc = 0.0
    for i, v in enumerate(s):
        acc += v
        if i >= period:
            acc -= s[i - period]
        out.append(acc / min(i + 1, period))
    return out

def rsi(closes: Sequence[float], period: int = 14) -> List[float]:
    c = _to_list(closes)
    if len(c) < 2:
        return [50.0] * len(c)
    gains = [0.0]
    losses = [0.0]
    for i in range(1, len(c)):
        ch = c[i] - c[i - 1]
        gains.append(max(ch, 0.0))
        losses.append(max(-ch, 0.0))
    avg_gain = sma(gains, period)
    avg_loss = sma(losses, period)
    out = []
    for g, l in zip(avg_gain, avg_loss):
        if l == 0:
            out.append(100.0)
        else:
            rs = g / l
            out.append(100.0 - (100.0 / (1.0 + rs)))
    return out

def macd(closes: Sequence[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[List[float], List[float], List[float]]:
    c = _to_list(closes)
    ema_fast = ema(c, fast)
    ema_slow = ema(c, slow)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_line = ema(macd_line, signal)
    hist = [m - s for m, s in zip(macd_line, signal_line)]
    return macd_line, signal_line, hist

def atr(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], period: int = 14) -> List[float]:
    h, l, c = _to_list(highs), _to_list(lows), _to_list(closes)
    if not h:
        return []
    trs = [h[0] - l[0]]
    for i in range(1, len(h)):
        tr = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
        trs.append(tr)
    return ema(trs, period)

def obv(closes: Sequence[float], volumes: Sequence[float]) -> List[float]:
    c, v = _to_list(closes), _to_list(volumes)
    out = [0.0]
    for i in range(1, len(c)):
        if c[i] > c[i - 1]:
            out.append(out[-1] + v[i])
        elif c[i] < c[i - 1]:
            out.append(out[-1] - v[i])
        else:
            out.append(out[-1])
    return out

def vwap(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], volumes: Sequence[float]) -> List[float]:
    h, l, c, v = _to_list(highs), _to_list(lows), _to_list(closes), _to_list(volumes)
    out: List[float] = []
    cum_tp_vol = 0.0
    cum_vol = 0.0
    for hi, lo, cl, vol in zip(h, l, c, v):
        tp = (hi + lo + cl) / 3.0
        cum_tp_vol += tp * vol
        cum_vol += max(vol, 1e-12)
        out.append(cum_tp_vol / cum_vol)
    return out

def slope(series: Sequence[float], lookback: int = 5) -> List[float]:
    s = _to_list(series)
    out: List[float] = []
    for i in range(len(s)):
        if i < lookback:
            out.append(0.0)
        else:
            denom = abs(s[i - lookback]) if abs(s[i - lookback]) > 1e-12 else 1e-12
            out.append((s[i] - s[i - lookback]) / denom)
    return out