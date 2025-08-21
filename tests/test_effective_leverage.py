import pytest
from scalp.trade_utils import effective_leverage


def test_effective_leverage_basic():
    lev = effective_leverage(
        entry_price=100.0,
        liquidation_price=90.0,
        position_margin=10.0,
        position_size=1.0,
    )
    assert lev == pytest.approx(10.0)


def test_effective_leverage_estimated_margin():
    lev = effective_leverage(
        entry_price=200.0,
        liquidation_price=180.0,
        position_margin=0.0,
        position_size=2.0,
    )
    # price diff 20 * size 2 -> margin 40; notional 400
    assert lev == pytest.approx(10.0)


def test_effective_leverage_short_position():
    lev = effective_leverage(
        entry_price=100.0,
        liquidation_price=110.0,
        position_margin=10.0,
        position_size=-1.5,
    )
    assert lev == pytest.approx(15.0)


def test_effective_leverage_invalid():
    assert effective_leverage(0, 0, 0, 0) == 0.0
