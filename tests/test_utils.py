import pytest
from bot import ema, cross, compute_position_size, CONFIG
from scalp.trade_utils import extract_available_balance


def test_ema_basic():
    data = [1, 2, 3, 4, 5]
    result = ema(data, 3)
    assert result == pytest.approx([1, 1.5, 2.25, 3.125, 4.0625])


def test_cross_up_down_none():
    assert cross(3, 2, 1, 2) == 1  # up cross
    assert cross(0.5, 1, 2, 1) == -1  # down cross
    assert cross(2, 2, 2, 2) == 0  # no cross


def test_compute_position_size():
    detail = {
        "data": [
            {
                "symbol": CONFIG["SYMBOL"],
                "contractSize": 0.001,
                "volUnit": 1,
                "minVol": 1,
            }
        ]
    }
    vol = compute_position_size(detail, equity_usdt=100.0, price=20000.0,
                                risk_pct=0.01, leverage=5)
    assert vol == 1


def test_compute_position_size_missing_symbol():
    with pytest.raises(ValueError):
        compute_position_size({"data": []}, 100.0, 1.0, 0.01, 5)


def test_extract_available_balance_fallback():
    assets = {
        "data": [
            {
                "currency": "USDT",
                "available": 0,
                "cashBalance": "150.5",
                "equity": "200",
            }
        ]
    }
    assert extract_available_balance(assets) == 150.5


def test_extract_available_balance_equity_only():
    assets = {
        "data": [
            {
                "currency": "USDT",
                "equity": "42",
            }
        ]
    }
    assert extract_available_balance(assets) == 42.0


def test_extract_available_balance_zero_available_returns_zero():
    assets = {
        "data": [
            {
                "currency": "USDT",
                "available": 0,
                "availableBalance": 0,
                "equity": "42",
            }
        ]
    }
    assert extract_available_balance(assets) == 0.0
