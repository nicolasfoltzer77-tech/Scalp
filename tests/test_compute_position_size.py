import os
import sys
import types
import pytest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
sys.modules['requests'] = types.ModuleType('requests')
from bot import compute_position_size  # noqa: E402


def test_compute_position_size_basic():
    contract_detail = {
        "data": [
            {
                "symbol": "BTC_USDT",
                "contractSize": 0.01,
                "volUnit": 1,
                "minVol": 1,
            }
        ]
    }
    vol = compute_position_size(contract_detail, equity_usdt=1000, price=50000,
                                risk_pct=0.01, leverage=10, symbol="BTC_USDT")
    assert vol == 1


def test_compute_position_size_symbol_not_found():
    contract_detail = {"data": [{"symbol": "ETH_USDT", "contractSize": 0.1}]}
    with pytest.raises(ValueError):
        compute_position_size(contract_detail, equity_usdt=1000, price=500,
                                risk_pct=0.01, leverage=10, symbol="BTC_USDT")


def test_compute_position_size_invalid_price():
    contract_detail = {
        "data": [
            {
                "symbol": "BTC_USDT",
                "contractSize": 0.01,
                "volUnit": 1,
                "minVol": 1,
            }
        ]
    }
    vol = compute_position_size(
        contract_detail,
        equity_usdt=1000,
        price=0,
        risk_pct=0.01,
        leverage=10,
        symbol="BTC_USDT",
    )
    assert vol == 0


def test_compute_position_size_respects_equity():
    contract_detail = {
        "data": [
            {
                "symbol": "BTC_USDT",
                "contractSize": 1,
                "volUnit": 1,
                "minVol": 1,
            }
        ]
    }
    vol = compute_position_size(
        contract_detail,
        equity_usdt=5,
        price=100,
        risk_pct=0.01,
        leverage=10,
        symbol="BTC_USDT",
    )
    assert vol == 0


def test_compute_position_size_leaves_fee_buffer():
    contract_detail = {
        "data": [
            {
                "symbol": "BTC_USDT",
                "contractSize": 1,
                "volUnit": 1,
                "minVol": 1,
            }
        ]
    }
    vol = compute_position_size(
        contract_detail,
        equity_usdt=100,
        price=100,
        risk_pct=1.0,
        leverage=1,
        symbol="BTC_USDT",
    )
    assert vol == 0


def test_compute_position_size_under_min_notional_returns_zero():
    contract_detail = {
        "data": [
            {
                "symbol": "PI_USDT",
                "contractSize": 1,
                "volUnit": 1,
                "minVol": 1,
                "minTradeUSDT": 5,
            }
        ]
    }
    vol = compute_position_size(
        contract_detail,
        equity_usdt=100,
        price=0.5,
        risk_pct=0.0001,
        leverage=20,
        symbol="PI_USDT",
    )
    assert vol == 0
