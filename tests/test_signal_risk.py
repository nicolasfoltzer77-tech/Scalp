import types
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
sys.modules['requests'] = types.ModuleType('requests')

from bot import (
    map_score_to_sig_level,
    compute_risk_params,
    prepare_order,
    Signal,
    CONFIG,
)


class DummyRisk:
    def __init__(self, pct: float) -> None:
        self.risk_pct = pct


def _contract_detail():
    return {
        "data": [
            {
                "symbol": "BTC_USDT",
                "contractSize": 0.001,
                "volUnit": 1,
                "minVol": 1,
                "minTradeUSDT": 5,
            }
        ]
    }


def test_score_to_level_mapping():
    assert map_score_to_sig_level(10) == 1
    assert map_score_to_sig_level(35) == 2
    assert map_score_to_sig_level(69.9) == 2
    assert map_score_to_sig_level(70) == 3


def test_risk_tables():
    rp, lev, cap = compute_risk_params(2, 3, 0.01, 20)
    assert rp == 0.01 * 1.25
    assert lev == int(20 * 0.75)
    assert cap == 0.55


def test_notional_cap():
    rm = DummyRisk(0.05)
    sig = Signal("BTC_USDT", "long", 10000, 9900, 10100, 10200, 1, score=80)
    available = 1000
    params = prepare_order(
        sig,
        _contract_detail(),
        equity_usdt=available,
        available_usdt=available,
        base_leverage=10,
        risk_mgr=rm,
        user_risk_level=2,
    )
    assert params["notional"] <= params["cap_ratio"] * available + 1e-6
