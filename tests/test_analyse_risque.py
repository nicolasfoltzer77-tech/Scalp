import os
import sys
import types

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
sys.modules['requests'] = types.SimpleNamespace(
    request=lambda *a, **k: None,
    post=lambda *a, **k: None,
    HTTPError=Exception,
)

from bot import analyse_risque  # noqa: E402


def make_contract_detail():
    return {
        "data": [
            {
                "symbol": "BTC_USDT",
                "contractSize": 0.01,
                "volUnit": 1,
                "minVol": 1,
            }
        ]
    }


def test_analyse_risque_limits_and_leverage():
    contract_detail = make_contract_detail()
    # Risk level 1: leverage halved, limit 1 position
    open_pos = [{"symbol": "BTC_USDT", "side": "long"}]
    vol, lev = analyse_risque(contract_detail, open_pos, 1000, 50000, 0.01, 10,
                               symbol="BTC_USDT", side="long", risk_level=1)
    assert lev == 5
    assert vol == 0  # already one long position

    # Risk level 2: base leverage, limit 3 positions
    open_pos = [
        {"symbol": "BTC_USDT", "side": "long"},
        {"symbol": "BTC_USDT", "side": "long"},
        {"symbol": "BTC_USDT", "side": "long"},
    ]
    vol, lev = analyse_risque(contract_detail, open_pos, 1000, 50000, 0.01, 10,
                               symbol="BTC_USDT", side="long", risk_level=2)
    assert lev == 10
    assert vol == 0

    # Risk level 3: leverage doubled, no existing position
    open_pos = []
    vol, lev = analyse_risque(contract_detail, open_pos, 1000, 50000, 0.01, 10,
                               symbol="BTC_USDT", side="long", risk_level=3)
    assert lev == 20
    assert vol == 1
