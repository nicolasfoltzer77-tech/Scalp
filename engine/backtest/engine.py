from __future__ import annotations
import math, statistics as stats
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple
import pandas as pd
from engine.core.signals import compute_signals

@dataclass
class BTParams:
    ema_fast: int = 20
    ema_slow: int = 50
    atr_period: int = 14
    trail_atr_mult: float = 2.0
    risk_pct_equity: float = 0.02
    cash: float = 10_000.0
    slippage_bps: int = 5

def grid_params() -> List[Dict[str, Any]]:
    grid: List[Dict[str, Any]] = []
    for fast in (9, 12, 20):
        for slow in (26, 50, 100):
            if slow <= fast: continue
            for atr_mult in (1.5, 2.0, 2.5):
                grid.append({"ema_fast": fast, "ema_slow": slow, "trail_atr_mult": atr_mult})
    return grid

def run_backtest_once(symbol: str, tf: str, ohlcv: pd.DataFrame, base_cfg_path: str | None = None, params: Dict[str, Any] | None = None):
    p = BTParams(**(params or {}))
    df = compute_signals(ohlcv, {
        "ema_fast": p.ema_fast, "ema_slow": p.ema_slow, "atr_period": p.atr_period
    })
    df = df.dropna().reset_index(drop=True)
    equity = p.cash
    pos_size = 0.0
    entry = 0.0
    trail = None
    trades: List[Dict[str, Any]] = []
    equity_curve: List[float] = [equity]

    for i in range(1, len(df)):
        row_prev = df.iloc[i-1]
        row = df.iloc[i]
        price = float(row["close"])
        atr = float(row["atr"])
        slip = price * (p.slippage_bps / 10_000.0)

        # entrée / sortie par signaux EMA
        sig = int(row_prev["signal"])  # on agit à la bougie suivante
        if pos_size == 0 and sig == 1:
            # calcule une taille simple basée sur le risque % et ATR
            risk_per_unit = max(atr, price * 0.002)  # garde-fou min
            risk_cash = equity * p.risk_pct_equity
            units = max(1.0, risk_cash / risk_per_unit)
            pos_size = units
            entry = price + slip
            trail = entry - p.trail_atr_mult * atr
        elif pos_size > 0:
            # mise à jour du trailing stop
            new_trail = price - p.trail_atr_mult * atr
            if trail is None or new_trail > trail:
                trail = new_trail
            # sortie par signal inverse ou cassure du trail
            exit_signal = (sig == -1) or (price < (trail or 0.0))
            if exit_signal:
                exit_price = price - slip
                pnl = (exit_price - entry) * pos_size
                equity += pnl
                trades.append({"entry": entry, "exit": exit_price, "pnl": pnl})
                pos_size = 0.0
                entry = 0.0
                trail = None

        equity_curve.append(equity if equity > 0 else 0.0)

    metrics = compute_metrics(equity_curve, trades)
    return {"equity_curve": equity_curve, "trades": trades, "metrics": metrics}

def compute_metrics(equity_curve: List[float], trades: List[Dict[str, Any]]) -> Dict[str, float]:
    if not equity_curve:
        return {"net_pnl_pct":0.0,"win_rate":0.0,"max_dd_pct":0.0,"sharpe":0.0,"trades":0,"score":0.0}
    start, end = equity_curve[0], equity_curve[-1]
    net_pnl_pct = (end - start) / start if start else 0.0
    # drawdown
    peak = -1e30; max_dd = 0.0
    for v in equity_curve:
        peak = max(peak, v)
        dd = (peak - v) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
    # sharpe approx (rendements par pas)
    if len(equity_curve) > 1:
        rets = []
        for i in range(1, len(equity_curve)):
            prev, cur = equity_curve[i-1], equity_curve[i]
            r = (cur - prev) / prev if prev else 0.0
            rets.append(r)
        if rets and (stats.pstdev(rets) or 0) > 0:
            sharpe = (stats.mean(rets) / stats.pstdev(rets)) * math.sqrt(252)
        else:
            sharpe = 0.0
    else:
        sharpe = 0.0
    wins = sum(1 for t in trades if t.get("pnl",0.0) > 0)
    wr = (wins / len(trades)) if trades else 0.0
    score = (sharpe * 2.0) + (net_pnl_pct * 1.0) - (max_dd * 0.5)
    return {"net_pnl_pct": float(net_pnl_pct), "win_rate": float(wr), "max_dd_pct": float(max_dd),
            "sharpe": float(sharpe), "trades": float(len(trades)), "score": float(score)}