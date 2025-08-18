import pytest

from scalp.risk import calc_risk_amount, calc_position_size


def test_calc_risk_amount_basic():
    assert calc_risk_amount(1000, 0.01) == 10.0


def test_calc_position_size_basic():
    # risk_amount = 1000 * 0.01 = 10; position size = 10 / 50 = 0.2
    assert calc_position_size(1000, 0.01, 50) == 0.2


@pytest.mark.parametrize("equity,risk_pct", [
    (0, 0.01),
    (-100, 0.01),
    (1000, 0),
    (1000, -0.1),
    (1000, 1.5),
])
def test_calc_risk_amount_invalid(equity, risk_pct):
    with pytest.raises(ValueError):
        calc_risk_amount(equity, risk_pct)


@pytest.mark.parametrize("stop_distance", [0, -1])
def test_calc_position_size_invalid_stop(stop_distance):
    with pytest.raises(ValueError):
        calc_position_size(1000, 0.01, stop_distance)
