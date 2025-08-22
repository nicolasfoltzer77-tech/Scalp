"""Run multi-symbol backtests from the command line.

Example:
    python backtest/run_multi.py --symbols "BTC/USDT,ETH/USDT" --exchange csv --csv-dir ./data
"""
import argparse
import csv
import json
import os
import random
import statistics
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from .engine import backtest_symbol


def _load_csv(symbol: str, timeframe: str, csv_dir: str) -> List[Dict[str, object]]:
    sym = symbol.replace("/", "")
    patterns = [
        f"{sym}-{timeframe}.csv",
        f"{sym}_{timeframe}.csv",
        f"{symbol.replace('/', '_')}-{timeframe}.csv",
        f"{symbol.replace('/', '_')}_{timeframe}.csv",
    ]
    for pat in patterns:
        path = os.path.join(csv_dir, pat)
        if os.path.exists(path):
            rows: List[Dict[str, object]] = []
            with open(path, newline="", encoding="utf8") as fh:
                reader = csv.DictReader(fh)
                for r in reader:
                    ts = datetime.fromtimestamp(float(r["timestamp"]) / 1000.0, tz=timezone.utc)
                    rows.append(
                        {
                            "timestamp": ts,
                            "open": float(r["open"]),
                            "high": float(r["high"]),
                            "low": float(r["low"]),
                            "close": float(r["close"]),
                            "volume": float(r["volume"]),
                        }
                    )
            return rows
    raise FileNotFoundError(f"CSV for {symbol} not found in {csv_dir}")


def load_data(symbols: List[str], exchange: str, timeframe: str, csv_dir: str | None) -> Dict[str, List[Dict[str, object]]]:
    data: Dict[str, List[Dict[str, object]]] = {}
    for sym in symbols:
        if exchange != "csv":
            raise ValueError("Only csv exchange supported in test environment")
        if not csv_dir:
            raise ValueError("csv_dir required")
        data[sym] = _load_csv(sym, timeframe, csv_dir)
    return data


def compute_metrics(trades: List[Dict[str, float]], equity_curve: List[Dict[str, float]], initial_equity: float) -> Dict[str, float]:
    trades_count = len(trades)
    pnl_usdt = sum(t["pnl_usdt"] for t in trades)
    pnl_pct = pnl_usdt / initial_equity * 100.0 if initial_equity else 0.0
    wins = [t for t in trades if t["pnl_usdt"] > 0]
    losses = [t for t in trades if t["pnl_usdt"] < 0]
    winrate = len(wins) / trades_count * 100.0 if trades_count else 0.0
    expectancy = statistics.mean([t["pnl_pct"] for t in trades]) if trades else 0.0
    profit_factor = sum(t["pnl_usdt"] for t in wins) / abs(sum(t["pnl_usdt"] for t in losses)) if losses else float("inf")
    peak = equity_curve[0]["equity"] if equity_curve else initial_equity
    max_dd = 0.0
    for p in equity_curve:
        if p["equity"] > peak:
            peak = p["equity"]
        dd = (peak - p["equity"]) / peak if peak else 0.0
        if dd > max_dd:
            max_dd = dd
    returns: List[float] = []
    prev = None
    for p in equity_curve:
        if prev is not None and prev > 0:
            returns.append((p["equity"] - prev) / prev)
        prev = p["equity"]
    sharpe = 0.0
    if returns:
        mean = statistics.mean(returns)
        std = statistics.pstdev(returns)
        if std:
            sharpe = mean / std * (len(returns) ** 0.5)
    avg_hold = statistics.mean([t["holding_s"] for t in trades]) if trades else 0.0
    turnover = sum(abs(t["notional"]) for t in trades) / initial_equity if trades else 0.0
    return {
        "trades": trades_count,
        "winrate_pct": winrate,
        "pnl_pct": pnl_pct,
        "pnl_usdt": pnl_usdt,
        "expectancy_pct": expectancy,
        "profit_factor": profit_factor,
        "max_drawdown_pct": max_dd * 100.0,
        "sharpe": sharpe,
        "avg_hold_s": avg_hold,
        "turnover": turnover,
    }


def run_backtest_multi(
    *,
    symbols: List[str],
    exchange: str,
    timeframe: str,
    csv_dir: str | None = None,
    fee_rate: float = 0.0,
    slippage_bps: float = 0.0,
    risk_pct: float = 0.01,
    initial_equity: float = 1000.0,
    leverage: float = 1.0,
    paper_constraints: bool = True,
    seed: int | None = None,
    out_dir: str = "./result",
    plot: bool = False,
    dry_run: bool = False,
) -> Tuple[List[Dict[str, float]], List[Dict[str, float]]]:
    if seed is not None:
        random.seed(seed)
    data = load_data(symbols, exchange, timeframe, csv_dir)
    os.makedirs(out_dir, exist_ok=True)

    per_symbol_summary: List[Dict[str, float]] = []
    all_trades: List[Dict[str, float]] = []
    equity_maps: Dict[str, List[Dict[str, float]]] = {}
    init_per_symbol = initial_equity / len(symbols)

    for sym in symbols:
        trades, eq = backtest_symbol(
            data[sym],
            sym,
            fee_rate=fee_rate,
            slippage_bps=slippage_bps,
            risk_pct=risk_pct,
            initial_equity=init_per_symbol,
            leverage=leverage,
            paper_constraints=paper_constraints,
            seed=seed,
        )
        all_trades.extend(trades)
        equity_maps[sym] = eq
        met = compute_metrics(trades, eq, init_per_symbol)
        row = {"symbol": sym}
        row.update(met)
        per_symbol_summary.append(row)
        if not dry_run:
            with open(os.path.join(out_dir, f"equity_curve_{sym.replace('/', '_')}.csv"), "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["timestamp", "equity"])
                for e in eq:
                    w.writerow([e["timestamp"].isoformat(), f"{e['equity']:.6f}"])

    # total equity curve based on trade order
    eq_total: List[Dict[str, float]] = []
    eq = initial_equity
    for tr in sorted(all_trades, key=lambda x: x["exit_time"]):
        eq += tr["pnl_usdt"]
        eq_total.append({"timestamp": tr["exit_time"], "equity": eq})
    total_metrics = compute_metrics(all_trades, eq_total, initial_equity)
    total_row = {"symbol": "TOTAL", **total_metrics, "avg_corr": 0.0}
    summary = per_symbol_summary + [total_row]

    if not dry_run:
        # summary csv
        cols = [
            "symbol",
            "trades",
            "winrate_pct",
            "pnl_pct",
            "pnl_usdt",
            "expectancy_pct",
            "profit_factor",
            "max_drawdown_pct",
            "sharpe",
            "avg_hold_s",
            "turnover",
            "avg_corr",
        ]
        with open(os.path.join(out_dir, "report_summary.csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(cols)
            for row in summary:
                w.writerow([row.get(c, "") for c in cols])
        # trades csv
        trade_cols = [
            "entry_time",
            "exit_time",
            "symbol",
            "side",
            "entry",
            "exit",
            "qty",
            "pnl_pct",
            "pnl_usdt",
            "fee_pct",
            "slippage_bps",
            "reason",
            "score",
            "notional",
            "holding_s",
        ]
        with open(os.path.join(out_dir, "report_trades.csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(trade_cols)
            for tr in all_trades:
                w.writerow([tr.get(c, "") if not isinstance(tr.get(c, ""), datetime) else tr.get(c).isoformat() for c in trade_cols])
        with open(os.path.join(out_dir, "equity_curve_total.csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["timestamp", "equity"])
            for e in eq_total:
                w.writerow([e["timestamp"].isoformat(), f"{e['equity']:.6f}"])
        with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf8") as fh:
            json.dump({
                "parameters": {
                    "symbols": symbols,
                    "exchange": exchange,
                    "timeframe": timeframe,
                    "fee_rate": fee_rate,
                    "slippage_bps": slippage_bps,
                    "risk_pct": risk_pct,
                    "initial_equity": initial_equity,
                    "leverage": leverage,
                    "paper_constraints": paper_constraints,
                    "seed": seed,
                },
                "summary": summary,
            }, fh, indent=2, default=str)
    # console output
    header = f"{'symbol':<10} {'trades':>6} {'win%':>6} {'pnl%':>8} {'pnl_usdt':>10}"
    print(header)
    for row in summary:
        print(
            f"{row['symbol']:<10} {int(row['trades']):>6} {row['winrate_pct']:>6.2f} {row['pnl_pct']:>8.2f} {row['pnl_usdt']:>10.2f}"
        )
    return summary, all_trades


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run multi-pair backtest")
    p.add_argument("--symbols", required=True)
    p.add_argument("--exchange", default="csv")
    p.add_argument("--timeframe", default="1m")
    p.add_argument("--csv-dir")
    p.add_argument("--fee-rate", type=float, default=0.0)
    p.add_argument("--slippage-bps", type=float, default=0.0)
    p.add_argument("--risk-pct", type=float, default=0.01)
    p.add_argument("--initial-equity", type=float, default=1000.0)
    p.add_argument("--leverage", type=float, default=1.0)
    p.add_argument("--paper-constraints", action="store_true")
    p.add_argument("--seed", type=int)
    p.add_argument("--out-dir", default="./result")
    p.add_argument("--plot", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    return p


def main(args: List[str] | None = None):
    parser = build_arg_parser()
    ns = parser.parse_args(args=args)
    symbols = [s.strip() for s in ns.symbols.split(",") if s.strip()]
    return run_backtest_multi(
        symbols=symbols,
        exchange=ns.exchange,
        timeframe=ns.timeframe,
        csv_dir=ns.csv_dir,
        fee_rate=ns.fee_rate,
        slippage_bps=ns.slippage_bps,
        risk_pct=ns.risk_pct,
        initial_equity=ns.initial_equity,
        leverage=ns.leverage,
        paper_constraints=ns.paper_constraints,
        seed=ns.seed,
        out_dir=ns.out_dir,
        plot=ns.plot,
        dry_run=ns.dry_run,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
