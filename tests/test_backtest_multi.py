import csv
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backtest.run_multi import run_backtest_multi
from scalp.strategy import Signal


def make_csv(tmp_path: Path, symbol: str, timeframe: str = "1m") -> None:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    filename = tmp_path / f"{symbol.replace('/', '')}-{timeframe}.csv"
    with open(filename, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for i in range(200):
            ts = int((start + timedelta(minutes=i)).timestamp() * 1000)
            price = 100 + i
            writer.writerow([ts, price, price * 1.02, price * 0.995, price, 1])


def simple_signal(symbol, ohlcv, equity, risk_pct, **kwargs):
    closes = ohlcv["close"]
    if len(closes) < 10:
        return None
    price = closes[-1]
    sl = price * 0.99
    tp = price * 1.01
    qty = equity * risk_pct / (price - sl)
    return Signal(symbol, "long", price, sl, tp, tp * 1.01, qty, score=1.0, reasons=["test"])


def random_signal(symbol, ohlcv, equity, risk_pct, **kwargs):
    if len(ohlcv["close"]) < 10 or random.random() > 0.3:
        return None
    price = ohlcv["close"][-1]
    sl = price * 0.99
    tp = price * 1.01
    qty = equity * risk_pct / (price - sl)
    return Signal(symbol, "long", price, sl, tp, tp * 1.01, qty)


def tiny_qty_signal(symbol, ohlcv, equity, risk_pct, **kwargs):
    closes = ohlcv["close"]
    if len(closes) < 10:
        return None
    price = closes[-1]
    sl = price * 0.99
    tp = price * 1.01
    return Signal(symbol, "long", price, sl, tp, tp * 1.01, 0.00005)


def find_row(summary, symbol):
    for row in summary:
        if row["symbol"] == symbol:
            return row
    raise KeyError(symbol)


def test_csv_multi_pairs(tmp_path, monkeypatch):
    for sym in ["BTC/USDT", "ETH/USDT"]:
        make_csv(tmp_path, sym)
    monkeypatch.setattr("scalp.strategy.generate_signal", simple_signal)
    monkeypatch.setattr("backtest.engine.generate_signal", simple_signal)
    out = tmp_path / "out"
    summary, trades = run_backtest_multi(
        symbols=["BTC/USDT", "ETH/USDT"],
        exchange="csv",
        timeframe="1m",
        csv_dir=str(tmp_path),
        fee_rate=0.0,
        slippage_bps=0.0,
        risk_pct=0.01,
        initial_equity=1000,
        leverage=1.0,
        paper_constraints=True,
        seed=42,
        out_dir=str(out),
        plot=False,
    )
    btc_trades = [t for t in trades if t["symbol"] == "BTC/USDT"]
    eth_trades = [t for t in trades if t["symbol"] == "ETH/USDT"]
    assert len(btc_trades) > 0 and len(eth_trades) > 0
    assert find_row(summary, "BTC/USDT")["pnl_usdt"] > 0
    total = find_row(summary, "TOTAL")["pnl_usdt"]
    assert pytest.approx(total) == find_row(summary, "BTC/USDT")["pnl_usdt"] + find_row(summary, "ETH/USDT")["pnl_usdt"]
    # files
    assert (out / "report_summary.csv").exists()
    assert (out / "report_trades.csv").exists()
    assert (out / "equity_curve_total.csv").exists()
    assert (out / "equity_curve_BTC_USDT.csv").exists()
    # columns in trades
    for col in ["entry_time", "exit_time", "symbol", "side", "entry", "exit", "pnl_pct", "pnl_usdt"]:
        assert col in trades[0]


def test_fee_slippage(tmp_path, monkeypatch):
    make_csv(tmp_path, "BTC/USDT")
    monkeypatch.setattr("scalp.strategy.generate_signal", simple_signal)
    monkeypatch.setattr("backtest.engine.generate_signal", simple_signal)
    summary1, _ = run_backtest_multi(
        symbols=["BTC/USDT"],
        exchange="csv",
        timeframe="1m",
        csv_dir=str(tmp_path),
        fee_rate=0.0,
        slippage_bps=0.0,
        out_dir=str(tmp_path / "o1"),
    )
    summary2, _ = run_backtest_multi(
        symbols=["BTC/USDT"],
        exchange="csv",
        timeframe="1m",
        csv_dir=str(tmp_path),
        fee_rate=0.01,
        slippage_bps=100,
        out_dir=str(tmp_path / "o2"),
    )
    pnl1 = find_row(summary1, "TOTAL")["pnl_usdt"]
    pnl2 = find_row(summary2, "TOTAL")["pnl_usdt"]
    assert pnl2 < pnl1


def test_paper_constraints(tmp_path, monkeypatch):
    make_csv(tmp_path, "BTC/USDT")
    monkeypatch.setattr("scalp.strategy.generate_signal", tiny_qty_signal)
    monkeypatch.setattr("backtest.engine.generate_signal", tiny_qty_signal)
    summary, trades = run_backtest_multi(
        symbols=["BTC/USDT"],
        exchange="csv",
        timeframe="1m",
        csv_dir=str(tmp_path),
        paper_constraints=True,
        out_dir=str(tmp_path / "o"),
    )
    assert all(t["qty"] >= 0.001 for t in trades)
    assert all(abs((t["qty"] * 10000) % 1) < 1e-9 for t in trades)
    assert all(t["entry"] * t["qty"] >= 5 - 1e-9 for t in trades)


def test_seed_reproducible(tmp_path, monkeypatch):
    make_csv(tmp_path, "BTC/USDT")
    monkeypatch.setattr("scalp.strategy.generate_signal", random_signal)
    monkeypatch.setattr("backtest.engine.generate_signal", random_signal)
    s1, t1 = run_backtest_multi(
        symbols=["BTC/USDT"],
        exchange="csv",
        timeframe="1m",
        csv_dir=str(tmp_path),
        seed=7,
        out_dir=str(tmp_path / "o1"),
    )
    s2, t2 = run_backtest_multi(
        symbols=["BTC/USDT"],
        exchange="csv",
        timeframe="1m",
        csv_dir=str(tmp_path),
        seed=7,
        out_dir=str(tmp_path / "o2"),
    )
    assert t1 == t2
    assert s1 == s2
