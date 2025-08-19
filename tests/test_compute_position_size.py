import os
import sys
import types
import pytest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
sys.modules['requests'] = types.ModuleType('requests')
from bot import compute_position_size  # noqa: E402


def test_compute_position_size_basic():
    qty = compute_position_size(equity_usdt=1000, price=50000, risk_pct=0.01)
    assert qty == 0  # 10 USDT / 50k -> 0 BTC


def test_compute_position_size_positive():
    qty = compute_position_size(equity_usdt=1000, price=100, risk_pct=0.1)
    assert qty == 1  # 100 USDT / 100 = 1


def test_compute_position_size_invalid():
    assert compute_position_size(0, 100, 0.1) == 0
    assert compute_position_size(1000, -1, 0.1) == 0
    assert compute_position_size(1000, 100, -0.1) == 0
