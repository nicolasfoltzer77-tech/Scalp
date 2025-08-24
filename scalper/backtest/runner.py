# scalper/backtest/runner.py
from __future__ import annotations
import argparse
import os
from typing import Dict, List
from scalper.strategy.factory import load_strategies_cfg
from scalper.backtest.engine import BacktestEngine

def run_once(
    symbol: str,
    timeframe: str,
    csv_path: str,
    strategies_cfg_path: str = "scalper/config/strategies.yml",
    csv_1h_path: str = "",
    equity: float = 1000.0,
    risk: float = 0.01,
    fees_bps: float = 6.0,
) -> Dict[str, float]:
    cfg = load_strategies_cfg(strategies_cfg_path)
    data = BacktestEngine.load_csv(csv_path)
    data_1h = BacktestEngine.load_csv(csv_1h_path) if csv_1h_path and os.path.isfile(csv_1h_path) else None

    eng = BacktestEngine(
        symbol=symbol, timeframe=timeframe, data=data, data_1h=data_1h,
        equity_start=equity, risk_pct=risk, fees_bps=fees_bps, strategies_cfg=cfg,
    )
    eng.run()
    eng.save_results()
    return eng.summary()

def main():
    ap = argparse.ArgumentParser(description="Runner Backtest (point d'entrée unique)")
    ap.add_argument("--symbol", required=True, help="ex: BTCUSDT")
    ap.add_argument("--tf", required=True, help="ex: 5m, 1h")
    ap.add_argument("--csv", required=True, help="CSV OHLCV principal (timestamp,open,high,low,close,volume)")
    ap.add_argument("--csv_1h", default="", help="CSV 1h (optionnel) pour filtre MTF")
    ap.add_argument("--cfg", default="scalper/config/strategies.yml", help="config stratégies (YAML/JSON)")
    ap.add_argument("--equity", type=float, default=1000.0)
    ap.add_argument("--risk", type=float, default=0.01)
    ap.add_argument("--fees_bps", type=float, default=6.0)
    args = ap.parse_args()

    summary = run_once(
        symbol=args.symbol, timeframe=args.tf, csv_path=args.csv,
        strategies_cfg_path=args.cfg, csv_1h_path=args.csv_1h,
        equity=args.equity, risk=args.risk, fees_bps=args.fees_bps,
    )
    print("== Résumé ==")
    print(summary)

if __name__ == "__main__":
    main()