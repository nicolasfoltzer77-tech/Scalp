import os, sys, types, pytest
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
sys.modules['requests'] = types.ModuleType('requests')

from bot import _estimate_margin
from scalp.trade_utils import compute_pnl_usdt


def _detail():
    return {"data": [{"symbol": "BTC_USDT", "contractSize": 0.001}]}


def test_notional_and_pnl_units():
    detail = _detail()
    notional, margin = _estimate_margin(detail, price=10000, vol=2, leverage=10)
    assert notional == pytest.approx(10000 * 0.001 * 2)
    pnl = compute_pnl_usdt(detail, 10000, 10100, 2, 1, symbol="BTC_USDT")
    assert pnl == pytest.approx((10100 - 10000) * 0.001 * 2)
