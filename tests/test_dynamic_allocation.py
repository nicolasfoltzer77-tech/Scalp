import math
from scalp.risk import adjust_risk_pct


def test_adjust_risk_pct_increase_decrease():
    base = 0.01
    assert adjust_risk_pct(base, win_streak=2, loss_streak=0) > base
    assert adjust_risk_pct(base, win_streak=0, loss_streak=2) < base


def test_adjust_risk_pct_bounds():
    assert math.isclose(
        adjust_risk_pct(0.05, win_streak=2, loss_streak=0, max_pct=0.05), 0.05
    )
    assert math.isclose(
        adjust_risk_pct(0.001, win_streak=0, loss_streak=2, min_pct=0.001), 0.001
    )
