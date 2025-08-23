import os, sys, types, pytest
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
sys.modules['requests'] = types.ModuleType('requests')

from scalper.trade_utils import (
    get_contract_size,
    notional as calc_notional,
    required_margin as calc_required_margin,
    compute_pnl_usdt,
    compute_pnl_with_fees,
)


def _detail():
    return {"data": [{"symbol": "BTC_USDT", "contractSize": 0.001}]}


def test_notional_and_pnl_units():
    detail = _detail()
    cs = get_contract_size(detail, "BTC_USDT")
    N = calc_notional(10000, 2, cs)
    assert N == pytest.approx(10000 * 0.001 * 2)
    margin = calc_required_margin(N, 10, 0.001, buffer=0.0)
    assert margin == pytest.approx(N / 10 + 0.001 * N)
    pnl = compute_pnl_usdt(detail, 10000, 10100, 2, 1, symbol="BTC_USDT")
    assert pnl == pytest.approx((10100 - 10000) * 0.001 * 2)
    pnl_net, pct = compute_pnl_with_fees(
        detail, 10000, 10100, 2, 1, 10, 0.001, symbol="BTC_USDT"
    )
    gross = (10100 - 10000) * cs * 2
    fees = 0.001 * (calc_notional(10000, 2, cs) + calc_notional(10100, 2, cs))
    expected = gross - fees
    expected_pct = expected / (N / 10) * 100
    assert pnl_net == pytest.approx(expected)
    assert pct == pytest.approx(expected_pct)
