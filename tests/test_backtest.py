import pytest

import bot


def test_backtest_trades_fee():
    trades = [
        {"symbol": "AAA", "entry": 100.0, "exit": 110.0, "side": 1},
        {"symbol": "BBB", "entry": 100.0, "exit": 90.0, "side": -1},
    ]
    pnl = bot.backtest_trades(trades, fee_rate=0.001)
    # AAA: 10% - 0.2% fee = 9.8%; BBB: 10% - 0.2% fee = 9.8%
    assert pnl == pytest.approx(19.6)
