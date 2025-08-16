import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from scalp.metrics import calc_pnl_pct


def test_calc_pnl_pct_long():
    assert calc_pnl_pct(100.0, 110.0, 1) == 10.0

def test_calc_pnl_pct_short():
    assert calc_pnl_pct(100.0, 90.0, -1) == 10.0
