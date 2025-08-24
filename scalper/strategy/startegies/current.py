# scalper/strategy/strategies/current.py
from __future__ import annotations
from typing import Optional, Any, Dict, List
from scalper.core.signal import Signal
from scalper.core import indicators as ta

def _extract_ohlcv(ohlcv: Any) -> Dict[str, List[float]]:
    cols = ("timestamp", "open", "high", "low", "close", "volume")

    def to_float_list(seq) -> List[float]:
        return [float(x) for x in seq]

    # pandas.DataFrame
    if hasattr(ohlcv, "columns"):
        missing = [c for c in cols if c not in ohlcv.columns]
        if missing:
            raise ValueError(f"Colonnes OHLCV manquantes: {missing}")
        return {k: to_float_list(ohlcv[k].tolist()) for k in cols}

    # dict de listes
    if isinstance(ohlcv, dict):
        missing = [c for c in cols if c not in ohlcv]
        if missing:
            raise ValueError(f"Clés OHLCV manquantes: {missing}")
        return {k: to_float_list(ohlcv[k]) for k in cols}

    # liste de dicts
    if isinstance(ohlcv, (list, tuple)) and ohlcv and isinstance(ohlcv[0], dict):
        out: Dict[str, List[float]] = {k: [] for k in cols}
        for row in ohlcv:
            for k in cols:
                out[k].append(float(row[k]))
        return out

    raise TypeError("Format OHLCV non supporté. Attendu DataFrame|dict de listes|liste de dicts.")

def _last(lst: List[float]) -> float:
    return float(lst[-1])

def _b(x: bool) -> int:
    return 1 if x else 0

def _score_to_quality(score: int, total: int) -> float:
    if total <= 0:
        return 0.0
    q = score / float(total)
    return max(0.0, min(1.0, q))

def generate_signal(
    *,
    symbol: str,
    timeframe: str,
    ohlcv: Any,
    equity: float,
    risk_pct: float = 0.01,
    ohlcv_15m: Optional[Any] = None,
    ohlcv_1h: Optional[Any] = None,
    **kwargs,
) -> Optional[Signal]:
    """
    Stratégie 'current' multi-indicateurs:
      - Tendance: EMA20/50/200 (+ pente EMA200 en 1h si dispo)
      - Momentum: RSI(14), MACD(12,26,9)
      - Confiance: OBV, VWAP, ATR
      - SL/TP: ATR-multipliers
    Retour: Signal ou None
    """
    data = _extract_ohlcv(ohlcv)
    ts, h, l, c, v = data["timestamp"], data["high"], data["low"], data["close"], data["volume"]
    n = len(c)
    if n < 230:  # besoin EMA200 + MACD warmup
        return None

    ema20 = ta.ema(c, 20)
    ema50 = ta.ema(c, 50)
    ema200 = ta.ema(c, 200)
    macd_line, macd_sig, macd_hist = ta.macd(c, 12, 26, 9)
    rsi14 = ta.rsi(c, 14)
    atr14 = ta.atr(h, l, c, 14)
    obv = ta.obv(c, v)
    vwap = ta.vwap(h, l, c, v)

    # MTF (facultatif)
    mtf_long = mtf_short = True
    reasons: List[str] = []
    if ohlcv_1h is not None:
        hd = _extract_ohlcv(ohlcv_1h)
        ema200_1h = ta.ema(hd["close"], 200)
        slope_1h = ta.slope(ema200_1h, lookback=5)
        mtf_long = _last(slope_1h) > 0
        mtf_short = _last(slope_1h) < 0
        reasons.append(f"MTF1h={'up' if mtf_long else ('down' if mtf_short else 'flat')}")

    cond_trend_long = _last(c) > _last(ema20) > _last(ema50) > _last(ema200)
    cond_mom_long = _last(macd_hist) > 0 and _last(rsi14) >= 55.0
    cond_vol_long = _last(obv) > obv[-5] and _last(atr14) > 0.0005 * _last(c)

    cond_trend_short = _last(c) < _last(ema20) < _last(ema50) < _last(ema200)
    cond_mom_short = _last(macd_hist) < 0 and _last(rsi14) <= 45.0
    cond_vol_short = _last(obv) < obv[-5] and _last(atr14) > 0.0005 * _last(c)

    score_L = sum([_b(cond_trend_long), _b(cond_mom_long), _b(cond_vol_long), _b(mtf_long), _b(_last(c) > _last(vwap))])
    score_S = sum([_b(cond_trend_short), _b(cond_mom_short), _b(cond_vol_short), _b(mtf_short), _b(_last(c) < _last(vwap))])
    total = 5

    side = None
    score = 0
    if score_L > score_S and score_L >= 3:
        side, score = "long", score_L
    elif score_S > score_L and score_S >= 3:
        side, score = "short", score_S
    if side is None:
        return None

    price = _last(c)
    vol = max(_last(atr14), 1e-8)
    atr_mult_sl, tp1_mult, tp2_mult = 1.5, 1.0, 2.0

    if side == "long":
        sl = price - atr_mult_sl * vol
        tp1 = price + tp1_mult * vol
        tp2 = price + tp2_mult * vol
    else:
        sl = price + atr_mult_sl * vol
        tp1 = price - tp1_mult * vol
        tp2 = price - tp2_mult * vol

    reasons += [
        f"side={side}",
        f"rsi={_last(rsi14):.1f}",
        f"macd_hist={_last(macd_hist):.5f}",
        f"atr={vol:.5f}",
        f"vwap_rel={'above' if price>_last(vwap) else 'below'}",
    ]

    return Signal(
        symbol=symbol, timeframe=timeframe, side=side, entry=price, sl=sl, tp1=tp1, tp2=tp2,
        score=float(score), quality=_score_to_quality(score, total), reasons=reasons,
        timestamp=int(_last(ts)), extra={"risk_pct": float(risk_pct)},
    )