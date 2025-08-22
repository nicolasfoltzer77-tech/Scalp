import os
import sys
import types
import pytest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
sys.modules['requests'] = types.ModuleType('requests')

from bot import compute_position_size, CONFIG


def _detail(vol_unit=1, min_vol=1, min_trade=5):
    return {
        "data": [
            {
                "symbol": "BTC_USDT",
                "contractSize": 0.001,
                "volUnit": vol_unit,
                "minVol": min_vol,
                "minTradeUSDT": min_trade,
            }
        ]
    }


def test_volume_zero_when_available_low():
    detail = _detail()
    vol = compute_position_size(
        detail,
        equity_usdt=1000,
        price=10000,
        risk_pct=0.01,
        leverage=10,
        symbol="BTC_USDT",
        available_usdt=0.5,
    )
    assert vol == 0


def test_margin_close_to_available():
    detail = _detail()
    CONFIG["FEE_RATE"] = 0.001
    available = 1.05
    vol = compute_position_size(
        detail,
        equity_usdt=1000,
        price=10000,
        risk_pct=1,
        leverage=10,
        symbol="BTC_USDT",
        available_usdt=available,
    )
    assert vol == 1
    notional = 10000 * 0.001 * vol
    fee = max(CONFIG.get("FEE_RATE", 0.0), 0.001) * notional
    required = (notional / 10 + fee) * 1.03
    assert required == pytest.approx(available, rel=0.05)


def test_respects_units_and_minimums():
    detail = _detail(vol_unit=2, min_vol=2, min_trade=5)
    vol = compute_position_size(
        detail,
        equity_usdt=1000,
        price=1000,
        risk_pct=1,
        leverage=5,
        symbol="BTC_USDT",
        available_usdt=1000,
    )
    assert vol % 2 == 0 and vol >= 2
