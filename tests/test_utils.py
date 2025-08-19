import pytest
import pytest

from bot import ema, cross, compute_position_size


def test_ema_basic():
    data = [1, 2, 3, 4, 5]
    result = ema(data, 3)
    assert result == pytest.approx([1, 1.5, 2.25, 3.125, 4.0625])


def test_cross_up_down_none():
    assert cross(3, 2, 1, 2) == 1  # up cross
    assert cross(0.5, 1, 2, 1) == -1  # down cross
    assert cross(2, 2, 2, 2) == 0  # no cross


def test_compute_position_size():
    vol = compute_position_size(equity_usdt=100.0, price=20000.0, risk_pct=0.05)
    assert vol == 0


def test_compute_position_size_invalid_inputs():
    assert compute_position_size(-100.0, 20000.0, 0.01) == 0
    assert compute_position_size(100.0, -1.0, 0.01) == 0
    assert compute_position_size(100.0, 1.0, -0.5) == 0
