import pytest

import bot


def test_backtest_trades_zero_fee():
    trades = [
        {"symbol": "AAA", "entry": 100.0, "exit": 110.0, "side": 1},
        {"symbol": "BBB", "entry": 100.0, "exit": 90.0, "side": -1},
    ]
    pnl = bot.backtest_trades(trades, fee_rate=0.001, zero_fee_pairs=["BBB"])
    # AAA: 10% - 0.2% fee = 9.8%; BBB: 10% no fee
    assert pnl == pytest.approx(19.8)
