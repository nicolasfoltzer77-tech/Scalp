

import os
import sys
import pytest
sys.path.append(os.path.dirname(os.path.dirname(__file__)))


from scalp.metrics import calc_rsi, calc_atr


def test_calc_rsi_uptrend():
    prices = list(range(1, 16))  # strictly increasing
    assert calc_rsi(prices, period=14) == pytest.approx(100.0)


def test_calc_rsi_downtrend():
    prices = list(range(15, 0, -1))  # strictly decreasing
    assert calc_rsi(prices, period=14) == pytest.approx(0.0)


def test_calc_atr_constant_range():
    highs = [10, 11, 12, 13, 14]
    lows = [9, 10, 11, 12, 13]
    closes = [9.5, 10.5, 11.5, 12.5, 13.5]
    assert calc_atr(highs, lows, closes, period=3) == pytest.approx(1.5)



def test_calc_rsi_invalid_inputs():
    with pytest.raises(ValueError):
        calc_rsi([1, 2, 3], period=0)
    with pytest.raises(ValueError):
        calc_rsi([1, 2, 3], period=5)


def test_calc_atr_invalid_inputs():
    with pytest.raises(ValueError):
        calc_atr([1, 2, 3], [1, 2], [1, 2, 3], period=2)
    with pytest.raises(ValueError):
        calc_atr([1, 2], [1, 1], [1, 1], period=3)
