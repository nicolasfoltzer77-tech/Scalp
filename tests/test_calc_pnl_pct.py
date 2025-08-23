import os
import sys
import pytest
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from scalper.metrics import calc_pnl_pct


def test_calc_pnl_pct_long():
    assert calc_pnl_pct(100.0, 110.0, 1) == 10.0

def test_calc_pnl_pct_short():
    assert calc_pnl_pct(100.0, 90.0, -1) == 10.0


def test_calc_pnl_pct_with_fee():
    # 10% move minus 0.1%*2 fees = 9.8%
    assert calc_pnl_pct(100.0, 110.0, 1, fee_rate=0.001) == pytest.approx(9.8)
