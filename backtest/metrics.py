from __future__ import annotations
import math
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class Trade:
    ts: int
    side: str
    entry: float
    exit: float
    pnl_abs: float
    pnl_pct: float
    dur_min: float

def equity_to_drawdown(equity: List[float]) -> float:
    peak = -1e18; maxdd = 0.0
    for v in equity:
        if v > peak: peak = v
        dd = 0.0 if peak == 0 else (peak - v) / peak
        if dd > maxdd: maxdd = dd
    return maxdd

def sharpe(returns: List[float], rf: float = 0.0, period_per_year: int = 365*24*12) -> float:
    # returns: per-bar (ex: par 5m) log or simple; ici simple
    if not returns: return 0.0
    mean = sum(returns)/len(returns)
    var = sum((r-mean)**2 for r in returns)/max(1, len(returns)-1)
    std = math.sqrt(var) if var>0 else 0.0
    if std == 0: return 0.0
    return (mean - rf) / std * math.sqrt(period_per_year)

def summarize(trades: List[Trade], equity: List[float], bar_returns: List[float], start_ts: int, end_ts: int) -> Dict:
    wins = [t for t in trades if t.pnl_abs > 0]
    losses = [t for t in trades if t.pnl_abs < 0]
    wr = len(wins)/len(trades) if trades else 0.0
    gross_win = sum(t.pnl_abs for t in wins)
    gross_loss = abs(sum(t.pnl_abs for t in losses))
    pf = (gross_win / gross_loss) if gross_loss > 0 else float('inf') if gross_win > 0 else 0.0
    mdd = equity_to_drawdown(equity)
    shp = sharpe(bar_returns)
    expectancy = (gross_win - gross_loss) / max(1, len(trades))
    n_years = max(1e-9, (end_ts - start_ts) / (365*24*3600*1000))
    cagr = (equity[-1]/equity[0])**(1/n_years) - 1 if equity and equity[0] > 0 else 0.0
    score = (wr*0.2) + (min(pf,3.0)/3.0*0.3) + (max(0.0,1.0-mdd)*0.3) + (max(0.0, min(shp/3,1.0))*0.2)
    return {
        "trades": len(trades),
        "winrate": wr, "pf": pf, "maxdd": mdd, "sharpe": shp,
        "expectancy": expectancy, "cagr": cagr, "score": score,
        "equity_start": equity[0] if equity else None,
        "equity_end": equity[-1] if equity else None,
    }