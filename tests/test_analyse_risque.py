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


def test_analyse_risque_limits_and_leverage():
    # Risk level 1: limit 1 position
    open_pos = [{"symbol": "BTC_USDT", "side": "long"}]
    vol = analyse_risque(open_pos, 1000, 50000, 0.01,
                         symbol="BTC_USDT", side="long", risk_level=1)
    assert vol == 0  # already one long position

    # Risk level 2: limit 2 positions
    open_pos = [{"symbol": "BTC_USDT", "side": "long"},
                {"symbol": "BTC_USDT", "side": "long"}]
    vol = analyse_risque(open_pos, 1000, 50000, 0.01,
                         symbol="BTC_USDT", side="long", risk_level=2)
    assert vol == 0

    # Risk level 3: no existing position
    open_pos = []
    vol = analyse_risque(open_pos, 1000, 50000, 0.01,
                         symbol="BTC_USDT", side="long", risk_level=3)
    assert vol == 0  # 10 USDT/50k -> 0 qty
