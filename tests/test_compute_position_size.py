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
