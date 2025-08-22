import json
import random

import pytest

from backtest import grid_search


def test_build_grid_sampling():
    param_lists = {
        "timeframe": ["1m", "5m", "15m"],
        "score_min": [50, 55, 60],
        "atr_min_ratio": [0.0015, 0.002, 0.003],
    }
    combos = grid_search.build_param_grid(param_lists, grid_max=6)
    assert len(combos) == 6
    tfs = {c["timeframe"] for c in combos}
    assert {"1m", "5m", "15m"}.issubset(tfs)


def test_run_grid_search_with_mock(tmp_path):
    calls = []

    def fake_run_backtest_multi(**kwargs):
        tf = kwargs.get("timeframe")
        risk = kwargs.get("risk_pct")
        # fabricate metrics based on params
        pf = {"1m": 1.5, "5m": 3.0}[tf]
        pf += risk  # tiny variation
        metrics = {
            "symbol": "TOTAL",
            "pnl_usdt": 100 * risk,
            "profit_factor": pf,
            "max_drawdown_pct": 5.0 if tf == "1m" else 3.0,
            "winrate_pct": 50.0,
            "trades": 40 if tf == "1m" else 30,
        }
        calls.append((tf, risk))
        return [metrics], []

    param_lists = {
        "timeframe": ["1m", "5m"],
        "risk_pct": [0.005, 0.01],
    }
    base_params = {
        "timeframe": "1m",
        "risk_pct": 0.005,
    }
    out_dir = tmp_path / "grid"
    grid_search.run_grid_search(
        symbols=["BTC/USDT"],
        exchange="csv",
        base_params=base_params,
        param_lists=param_lists,
        grid_max=4,
        csv_dir="/dev/null",
        out_dir=str(out_dir),
        run_func=fake_run_backtest_multi,
    )
    best = json.loads((out_dir / "best_config.json").read_text())
    # best PF should be timeframe 5m risk 0.01
    assert best["params"]["timeframe"] == "5m"
    assert best["params"]["risk_pct"] == 0.01
    assert len(calls) == 4


def test_parse_hours():
    assert grid_search.parse_hours("7-11,13-17") == [7, 8, 9, 10, 11, 13, 14, 15, 16, 17]


def test_deterministic_results(tmp_path):
    def fake_run_backtest_multi(**kwargs):
        # metrics vary with global random state
        pf = random.uniform(1.0, 3.0)
        metrics = {
            "symbol": "TOTAL",
            "pnl_usdt": random.uniform(-10, 10),
            "profit_factor": pf,
            "max_drawdown_pct": random.uniform(1, 5),
            "winrate_pct": 50.0,
            "trades": random.randint(10, 50),
        }
        return [metrics], []

    param_lists = {"timeframe": ["1m", "5m"]}
    base_params = {"timeframe": "1m"}
    out_dir = tmp_path / "grid"
    res1 = grid_search.run_grid_search(
        symbols=["BTC/USDT"],
        exchange="csv",
        base_params=base_params,
        param_lists=param_lists,
        grid_max=2,
        csv_dir="/dev/null",
        out_dir=str(out_dir),
        seed=42,
        run_func=fake_run_backtest_multi,
    )
    best1 = json.loads((out_dir / "best_config.json").read_text())
    # run again
    out_dir2 = tmp_path / "grid2"
    res2 = grid_search.run_grid_search(
        symbols=["BTC/USDT"],
        exchange="csv",
        base_params=base_params,
        param_lists=param_lists,
        grid_max=2,
        csv_dir="/dev/null",
        out_dir=str(out_dir2),
        seed=42,
        run_func=fake_run_backtest_multi,
    )
    best2 = json.loads((out_dir2 / "best_config.json").read_text())
    assert best1 == best2
    # also ensure results object same best params
    assert res1[0].params == res2[0].params
