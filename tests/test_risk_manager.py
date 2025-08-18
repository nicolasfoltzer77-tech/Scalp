from scalp import RiskManager


def test_kill_switch_triggered() -> None:
    rm = RiskManager(max_daily_loss_pct=2.0, max_positions=1)
    rm.record_trade(-1.0)
    rm.record_trade(-1.5)
    assert rm.kill_switch is True


def test_pause_and_can_open() -> None:
    rm = RiskManager(max_daily_loss_pct=10.0, max_positions=1)
    rm.record_trade(-0.5)
    rm.record_trade(-0.6)
    rm.record_trade(-0.7)
    assert rm.pause_duration() == 15 * 60
    rm.record_trade(-0.8)
    rm.record_trade(-0.9)
    assert rm.pause_duration() == 60 * 60
    assert rm.can_open(0) is True
    assert rm.can_open(1) is False
