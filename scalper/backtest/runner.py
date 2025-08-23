# scalper/backtest/runner.py
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .market_data import hybrid_loader

# ------------------------------------------------------------
@dataclass
class BTConfig:
    timeframe: str = "5m"
    cash: float = 10_000.0
    risk_pct: float = 0.005          # 0.5%
    fees_bps: float = 6.0
    slippage_bps: float = 0.0
    limit: int = 1000
    data_dir: str = "data"
    out_dir: str = "result/backtests"
    strategy_name: str = "current"
    start: Optional[str] = None
    end: Optional[str] = None

def load_strategy(name: str) -> Callable[[pd.DataFrame, Dict], Tuple[pd.Series, pd.Series]]:
    try:
        from scalper.signals.factory import load_signal
        fn = load_signal(name)
        return lambda df, params: fn(df=df, **params)
    except Exception:
        def ema_cross(df: pd.DataFrame, params: Dict) -> Tuple[pd.Series, pd.Series]:
            f, s = params.get("fast", 12), params.get("slow", 26)
            ema_f = df["close"].ewm(span=f, adjust=False).mean()
            ema_s = df["close"].ewm(span=s, adjust=False).mean()
            entry = (ema_f > ema_s) & (ema_f.shift(1) <= ema_s.shift(1))
            exit_ = (ema_f < ema_s) & (ema_f.shift(1) >= ema_s.shift(1))
            return entry.fillna(False), exit_.fillna(False)
        return ema_cross

def _bps_to_frac(bps: float) -> float:
    return float(bps) / 10_000.0

def make_loader(data_dir: str, limit: int) -> Callable[[str, str, Optional[str], Optional[str]], pd.DataFrame]:
    return hybrid_loader(
        data_dir=data_dir,
        use_cache_first=True,
        min_rows=100,
        refill_if_stale=True,
        network_limit=limit,
    )

# ------------------------------------------------------------
def run_single(symbol: str, cfg: BTConfig, strat_params: Optional[Dict]=None) -> Dict:
    strat_params = strat_params or {}
    load = make_loader(cfg.data_dir, cfg.limit)
    df = load(symbol, cfg.timeframe, cfg.start, cfg.end)

    strat = load_strategy(cfg.strategy_name)
    entry, exit_ = strat(df, strat_params)

    cash = cfg.cash
    qty = 0.0
    fee = _bps_to_frac(cfg.fees_bps)
    slp = _bps_to_frac(cfg.slippage_bps)

    equity = []
    trades = []

    for ts, row in df.iterrows():
        price = float(row["close"])

        # sortie prioritaire
        if qty > 0 and bool(exit_.get(ts, False)):
            px = price * (1.0 - slp)
            cash += qty * px * (1.0 - fee)
            trades.append({"timestamp": ts, "symbol": symbol, "side": "sell", "price": px, "qty": qty})
            qty = 0.0

        if qty == 0 and bool(entry.get(ts, False)):
            risk_cap = cash * cfg.risk_pct
            if risk_cap > 0:
                px = price * (1.0 + slp)
                new_qty = max(risk_cap / px, 0.0)
                cost = new_qty * px * (1.0 + fee)
                if cost <= cash:
                    cash -= cost
                    qty = new_qty
                    trades.append({"timestamp": ts, "symbol": symbol, "side": "buy", "price": px, "qty": qty})

        equity.append((ts, cash + qty * price))

    eq_df = pd.DataFrame(equity, columns=["timestamp","equity"]).set_index("timestamp")
    vals = eq_df["equity"].values
    ret = vals[-1]/vals[0]-1.0 if len(vals) > 1 else 0.0
    dd = 0.0; peak = -1e18
    for v in vals:
        peak = max(peak, v); dd = min(dd, v/peak - 1.0)

    metrics = {
        "symbol": symbol,
        "n_bars": int(len(df)),
        "n_trades": int(len(trades)),
        "return": float(ret),
        "max_drawdown": float(dd),
        "final_equity": float(vals[-1] if len(vals) else cfg.cash),
        "timeframe": cfg.timeframe,
        "fees_bps": cfg.fees_bps,
        "slippage_bps": cfg.slippage_bps,
        "risk_pct": cfg.risk_pct,
        "cash_start": cfg.cash,
    }
    return {"equity": eq_df, "trades": pd.DataFrame(trades), "metrics": metrics}

def run_multi(symbols: List[str], cfg: BTConfig, strat_params: Optional[Dict]=None) -> Dict:
    pieces = []
    per_symbol = {}
    all_trades = []
    for s in symbols:
        res = run_single(s, cfg, strat_params)
        per_symbol[s] = res["metrics"]
        pieces.append(res["equity"].rename(columns={"equity": s}))
        all_trades.append(res["trades"].assign(symbol=s))
    equity = pd.concat(pieces, axis=1).fillna(method="ffill").fillna(method="bfill")
    equity["equity"] = equity.mean(axis=1)
    final = float(equity["equity"].iloc[-1]) if len(equity) else cfg.cash
    ret = final / cfg.cash - 1.0
    metrics = {
        "mode": "multi",
        "symbols": symbols,
        "timeframe": cfg.timeframe,
        "cash_start": cfg.cash,
        "final_equity": final,
        "return": float(ret),
        "fees_bps": cfg.fees_bps,
        "slippage_bps": cfg.slippage_bps,
        "risk_pct": cfg.risk_pct,
        "per_symbol": per_symbol,
    }
    trades = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame(columns=["timestamp","symbol","side","price","qty"])
    return {"equity": equity[["equity"]], "trades": trades, "metrics": metrics}

def save_results(tag: str, res: Dict, out_dir: str) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    root = Path(out_dir) / f"{stamp}-{tag}"
    root.mkdir(parents=True, exist_ok=True)
    res["equity"].to_csv(root / "equity_curve.csv")
    res["trades"].to_csv(root / "trades.csv", index=False)
    with open(root / "metrics.json", "w") as f:
        json.dump(res["metrics"], f, indent=2)
    return root

# CLI optionnel
def _parse_args():
    import argparse
    p = argparse.ArgumentParser(description="Runner de backtest unifié (mono/multi)")
    p.add_argument("--symbols", default="BTCUSDT,ETHUSDT")
    p.add_argument("--timeframe", default="5m")
    p.add_argument("--cash", type=float, default=10_000)
    p.add_argument("--risk", type=float, default=0.005)
    p.add_argument("--fees_bps", type=float, default=6.0)
    p.add_argument("--slip_bps", type=float, default=0.0)
    p.add_argument("--limit", type=int, default=1000)
    p.add_argument("--data_dir", default="data")
    p.add_argument("--out_dir", default="result/backtests")
    p.add_argument("--strategy", default="current")
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    return p.parse_args()

def main():
    args = _parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    cfg = BTConfig(
        timeframe=args.timeframe, cash=args.cash, risk_pct=args.risk,
        fees_bps=args.fees_bps, slippage_bps=args.slip_bps, limit=args.limit,
        data_dir=args.data_dir, out_dir=args.out_dir, strategy_name=args.strategy,
        start=args.start, end=args.end,
    )
    tag = f"{args.timeframe}-{args.strategy}-{len(symbols)}sym"
    if len(symbols) == 1:
        res = run_single(symbols[0], cfg)
    else:
        res = run_multi(symbols, cfg)
    path = save_results(tag, res, cfg.out_dir)
    print(f"[✓] Backtest terminé → {path}")

if __name__ == "__main__":
    main()