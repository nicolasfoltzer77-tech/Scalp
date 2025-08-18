from scalp.risk import dynamic_risk_pct


def test_risk_pct_decreases_after_loss():
    assert dynamic_risk_pct(0.02, -1.0, "B") < 0.02


def test_risk_pct_increases_with_quality_A():
    assert dynamic_risk_pct(0.02, 1.0, "A") > 0.02
