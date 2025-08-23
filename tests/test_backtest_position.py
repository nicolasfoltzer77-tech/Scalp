import os
import sys
import pytest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from scalper.metrics import backtest_position


def test_backtest_position_long():
    prices = [100.0, 110.0, 120.0]
    assert backtest_position(prices, 0, 2, 1) is True


def test_backtest_position_short():
    prices = [100.0, 90.0, 80.0]
    assert backtest_position(prices, 0, 2, -1) is True


def test_backtest_position_incoherent():
    prices = [100.0, 110.0, 120.0]
    assert backtest_position(prices, 0, 2, -1) is False


def test_backtest_position_bad_indices():
    prices = [100.0, 110.0]
    with pytest.raises(ValueError):
        backtest_position(prices, 1, 0, 1)
