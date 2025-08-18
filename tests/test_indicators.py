import pytest

from scalp.metrics import calc_rsi, calc_atr


def test_calc_rsi_uptrend():
    prices = list(range(1, 16))  # strictly increasing
    assert calc_rsi(prices, period=14) == pytest.approx(100.0)


def test_calc_rsi_downtrend():
    prices = list(range(15, 0, -1))  # strictly decreasing
    assert calc_rsi(prices, period=14) == pytest.approx(0.0)


def test_calc_rsi_flat():
    prices = [1.0] * 15  # no movement
    assert calc_rsi(prices, period=14) == pytest.approx(50.0)


def test_calc_atr_constant_range():
    highs = [10, 11, 12, 13, 14]
    lows = [9, 10, 11, 12, 13]
    closes = [9.5, 10.5, 11.5, 12.5, 13.5]
    assert calc_atr(highs, lows, closes, period=3) == pytest.approx(1.5)


@pytest.mark.parametrize("prices, period", [([1, 2, 3], 0), ([1, 2, 3], 5)])
def test_calc_rsi_invalid_inputs(prices, period):
    with pytest.raises(ValueError):
        calc_rsi(prices, period=period)


@pytest.mark.parametrize(
    "highs, lows, closes, period",
    [
        ([1, 2, 3], [1, 2], [1, 2, 3], 2),
        ([1, 2], [1, 1], [1, 1], 3),
    ],
)
def test_calc_atr_invalid_inputs(highs, lows, closes, period):
    with pytest.raises(ValueError):
        calc_atr(highs, lows, closes, period=period)
