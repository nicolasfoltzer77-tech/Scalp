from __future__ import annotations

import argparse
from scalper.backtest.runner import run_multi, csv_loader_factory

def create_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="backtest", description="Backtest multi symboles / multi timeframes")
    p.add_argument("--symbols", required=True, help="Liste, ex: BTCUSDT,ETHUSDT,SOLUSDT")
    p.add_argument("--timeframes", required=True, help="Liste, ex: 1m,5m,15m")
    p.add_argument("--data-dir", default="data", help="Répertoire CSV OHLCV")
    p.add_argument("--out-dir", default="result", help="Répertoire de sortie")
    p.add_argument("--cash", type=float, default=10_000.0)
    p.add_argument("--risk", type=float, default=0.005, help="risk_pct par trade (0.005 = 0.5%)")
    p.add_argument("--slippage-bps", type=float, default=1.5)
    return p

def main(argv: list[str] | None = None) -> int:
    p = create_parser()
    a = p.parse_args(argv)
    symbols = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    tfs = [t.strip() for t in a.timeframes.split(",") if t.strip()]
    loader = csv_loader_factory(a.data_dir)
    run_multi(
        symbols=symbols,
        timeframes=tfs,
        loader=loader,
        out_dir=a.out_dir,
        initial_cash=a.cash,
        risk_pct=a.risk,
        slippage_bps=a.slippage_bps,
    )
    print(f"✅ Backtests terminés → {a.out_dir}/ (equity_curve/trades/fills/metrics/summary)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())