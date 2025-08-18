"""Core trading strategy components for scalping EMA/VWAP/RSI/ATR.

This module implements a minimal but functional version of the strategy
outlined in the project specification.  The focus is on pure Python
implementations so the logic can easily be unit tested without requiring
external services or heavy third‑party dependencies.

The strategy is deliberately stateless; functions operate on passed data and
return simple data structures.  This makes it easy to plug the logic into
real‑time trading loops or backtest engines.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, List, Dict, Optional, Tuple, Any

from .metrics import calc_rsi, calc_atr, calc_pnl_pct
from .risk import calc_position_size

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ema(series: Sequence[float], window: int) -> List[float]:
    """Return the exponential moving average of *series*.

    The first value is the raw input to remain consistent with most trading
    platforms.  ``window`` must be positive; when it equals ``1`` the input is
    returned unchanged.
    """

    if window <= 1 or not series:
        return list(series)
    k = 2.0 / (window + 1.0)
    out: List[float] = [float(series[0])]
    prev = out[0]
    for x in series[1:]:
        prev = float(x) * k + prev * (1.0 - k)
        out.append(prev)
    return out

def vwap(highs: Sequence[float], lows: Sequence[float],
         closes: Sequence[float], volumes: Sequence[float]) -> float:
    """Compute the volume weighted average price (VWAP).

    Parameters
    ----------
    highs, lows, closes, volumes: Sequence[float]
        Matching sequences for the period considered.
    """

    tp_vol = 0.0
    vol_sum = 0.0
    for h, low, c, v in zip(highs, lows, closes, volumes):
        tp = (h + low + c) / 3.0
        tp_vol += tp * v
        vol_sum += v
    return tp_vol / vol_sum if vol_sum else 0.0

def obv(closes: Sequence[float], volumes: Sequence[float]) -> List[float]:
    """Return the On Balance Volume (OBV) series."""

    if not closes:
        return []
    out: List[float] = [0.0]
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            out.append(out[-1] + volumes[i])
        elif closes[i] < closes[i - 1]:
            out.append(out[-1] - volumes[i])
        else:
            out.append(out[-1])
    return out


def cross(last_fast: float, last_slow: float, prev_fast: float, prev_slow: float) -> int:
    """Detect a crossing between two series.

    Returns ``1`` for a bullish crossover, ``-1`` for a bearish crossover and
    ``0`` otherwise.
    """

    if prev_fast <= prev_slow and last_fast > last_slow:
        return 1
    if prev_fast >= prev_slow and last_fast < last_slow:
        return -1
    return 0

# ---------------------------------------------------------------------------
# Pair selection
# ---------------------------------------------------------------------------

def scan_pairs(
    client: Any,
    *,
    zero_fee_pairs: Sequence[str],
    volume_min: float = 5_000_000,
    max_spread_bps: float = 5.0,
    top_n: int = 20,
) -> List[Dict[str, Any]]:
    """First level market scan.

    Only pairs with zero fees, sufficient 24h volume and tight spreads are
    returned.  The implementation mirrors the behaviour of ``filter_trade_pairs``
    found in :mod:`bot` but lives in a dedicated module so it can be reused in
    different contexts.
    """

    tick = client.get_ticker()
    data = tick.get("data") if isinstance(tick, dict) else []
    if not isinstance(data, list):
        data = [data]

    zero_fee = set(zero_fee_pairs)
    eligible: List[Dict[str, Any]] = []
    for row in data:
        sym = row.get("symbol")
        if not sym or sym not in zero_fee:
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
        eligible.append(row)

    eligible.sort(key=lambda r: float(r.get("volume", 0)), reverse=True)
    return eligible[:top_n]

def select_active_pairs(
    client: Any,
    pairs: Sequence[Dict[str, Any]],
    *,
    interval: str = "Min5",
    ema_fast: int = 20,
    ema_slow: int = 50,
    atr_period: int = 14,
    top_n: int = 5,
) -> List[Dict[str, Any]]:
    """Second level scan retaining 3–5 pairs with active momentum.

    Momentum is determined by the relative position of ``EMA20`` and ``EMA50``
    while the Average True Range identifies pairs exhibiting strong movement.
    The function returns the original ticker information augmented with the
    computed ``atr`` so callers can make further decisions.
    """

    results: List[Tuple[float, Dict[str, Any]]] = []
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
        if efast[-1] == eslow[-1]:  # no momentum
            continue
        atr = calc_atr(highs, lows, closes, atr_period)
        results.append((atr, info))

    results.sort(key=lambda r: r[0], reverse=True)
    return [info for _, info in results[:top_n]]

# ---------------------------------------------------------------------------
# Signal generation
# ---------------------------------------------------------------------------

@dataclass
class Signal:
    """Trading signal with risk parameters."""

    symbol: str
    side: str  # "long" or "short"
    price: float
    sl: float
    tp1: float
    tp2: float
    qty: float


def generate_signal(
    symbol: str,
    ohlcv: Dict[str, Sequence[float]],
    *,
    equity: float,
    risk_pct: float,
) -> Optional[Signal]:
    """Return a trading :class:`Signal` if conditions are met.

    ``ohlcv`` must contain ``open``, ``high``, ``low``, ``close`` and ``volume``
    sequences ordered from oldest to newest.  The function checks the following
    rules:

    * price positioned relative to VWAP and EMA20/EMA50 trend
    * RSI(14) crossing key levels (40/60)
    * OBV rising or high short‑term volume
    * Dynamic ATR‑based stop‑loss and take‑profit
    * Position sizing via ``calc_position_size``
    """

    closes = [float(x) for x in ohlcv.get("close", [])]
    highs = [float(x) for x in ohlcv.get("high", [])]
    lows = [float(x) for x in ohlcv.get("low", [])]
    vols = [float(x) for x in ohlcv.get("volume", [])]
    if len(closes) < 60 or len(highs) != len(lows) or len(closes) != len(highs):
        return None

    price = closes[-1]
    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)
    v = vwap(highs, lows, closes, vols)
    obv_series = obv(closes, vols)
    obv_rising = obv_series[-1] > obv_series[-2]
    vol_last3 = sum(vols[-3:])
    vol_ma20 = sum(vols[-20:]) / 20.0
    vol_rising = vol_last3 > vol_ma20

    # RSI crossing logic
    rsi_curr = calc_rsi(closes[-15:], 14)
    rsi_prev = calc_rsi(closes[-16:-1], 14)

    atr = calc_atr(highs, lows, closes, 14)
    sl_dist = 0.5 * atr
    tp1_dist = 1.0 * atr
    tp2_dist = 1.5 * atr

    def _size(dist: float) -> float:
        return calc_position_size(equity, risk_pct, dist)

    if (
        price > v
        and ema20[-1] > ema50[-1]
        and rsi_prev <= 40 < rsi_curr
        and (obv_rising or vol_rising)
    ):
        sl = price - sl_dist
        tp1 = price + tp1_dist
        tp2 = price + tp2_dist
        qty = _size(sl_dist)
        return Signal(symbol, "long", price, sl, tp1, tp2, qty)

    if (
        price < v
        and ema20[-1] < ema50[-1]
        and rsi_prev >= 60 > rsi_curr
        and (obv_series[-1] < obv_series[-2] or vol_rising)
    ):
        sl = price + sl_dist
        tp1 = price - tp1_dist
        tp2 = price - tp2_dist
        qty = _size(sl_dist)
        return Signal(symbol, "short", price, sl, tp1, tp2, qty)

    return None

# ---------------------------------------------------------------------------
# Risk limits
# ---------------------------------------------------------------------------

@dataclass
class RiskManager:
    """Utility class implementing kill switch and loss limits."""

    max_daily_loss_pct: float
    max_positions: int
    aggressive: bool = False

    def __post_init__(self) -> None:
        self.reset_day()

    def reset_day(self) -> None:
        self.daily_loss_pct = 0.0
        self.consecutive_losses = 0
        self.kill_switch = False

    def record_trade(self, pnl_pct: float) -> None:
        if pnl_pct < 0:
            self.consecutive_losses += 1
            self.daily_loss_pct += pnl_pct
        else:
            self.consecutive_losses = 0
        if self.daily_loss_pct <= -self.max_daily_loss_pct:
            self.kill_switch = True

    def pause_duration(self) -> int:
        if self.consecutive_losses >= 5:
            return 60 * 60
        if self.consecutive_losses >= 3:
            return 15 * 60
        return 0

    def can_open(self, current_positions: int) -> bool:
        return (not self.kill_switch) and current_positions < self.max_positions

# ---------------------------------------------------------------------------
# Backtesting utilities
# ---------------------------------------------------------------------------

def max_drawdown(equity_curve: Sequence[float]) -> float:
    peak = equity_curve[0]
    mdd = 0.0
    for x in equity_curve:
        if x > peak:
            peak = x
        dd = (peak - x) / peak * 100.0
        if dd > mdd:
            mdd = dd
    return mdd

def backtest(
    trades: Sequence[Dict[str, Any]],
    *,
    equity_start: float = 1_000.0,
    fee_rate: float = 0.0,
    zero_fee_pairs: Optional[Sequence[str]] = None,
) -> Dict[str, float]:
    """Evaluate a list of trade dictionaries.

    Each trade must provide ``symbol``, ``entry``, ``exit``, ``side`` and may
    optionally include ``duration`` in minutes.  Results are aggregated into
    common performance metrics to quickly evaluate the strategy.
    """

    zero_fee = set(zero_fee_pairs or [])
    equity = equity_start
    equity_curve = [equity]
    pnl_pct_list: List[float] = []
    wins = losses = 0
    win_sum = loss_sum = 0.0
    total_duration = 0.0

    for t in trades:
        fr = 0.0 if t.get("symbol") in zero_fee else fee_rate
        pnl_pct = calc_pnl_pct(t["entry"], t["exit"], t["side"], fr)
        pnl_pct_list.append(pnl_pct)
        if pnl_pct >= 0:
            wins += 1
            win_sum += pnl_pct
        else:
            losses += 1
            loss_sum += pnl_pct
        equity *= 1 + pnl_pct / 100.0
        equity_curve.append(equity)
        total_duration += float(t.get("duration", 0.0))

    pnl_pct_total = sum(pnl_pct_list)
    pnl_usdt = equity - equity_start
    profit_factor = (win_sum / abs(loss_sum)) if loss_sum else float("inf")
    winrate = wins / len(trades) * 100.0 if trades else 0.0
    mdd = max_drawdown(equity_curve)
    avg_trade_time = total_duration / len(trades) if trades else 0.0
    exposure = total_duration  # in minutes, callers can normalise if desired
    # Sharpe ratio based on per-trade returns
    if len(pnl_pct_list) > 1:
        mean = sum(pnl_pct_list) / len(pnl_pct_list)
        var = sum((r - mean) ** 2 for r in pnl_pct_list) / (len(pnl_pct_list) - 1)
        sharpe = mean / (var ** 0.5) if var > 0 else 0.0
    else:
        sharpe = 0.0

    return {
        "pnl_usdt": pnl_usdt,
        "pnl_pct": pnl_pct_total,
        "profit_factor": profit_factor,
        "winrate": winrate,
        "max_drawdown": mdd,
        "avg_trade_time": avg_trade_time,
        "exposure": exposure,
        "sharpe": sharpe,
    }
