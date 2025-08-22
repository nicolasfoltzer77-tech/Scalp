import os
import sys
import types

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
sys.modules['requests'] = types.ModuleType('requests')

from bot import _apply_contract_checks


def _detail():
    return {
        "data": [
            {
                "symbol": "BTC_USDT",
                "contractSize": 1,
                "volUnit": 5,
                "minVol": 10,
                "minTradeUSDT": 5,
            }
        ]
    }


def test_min_qty_floor_and_validation():
    detail = _detail()
    vol, N, req = _apply_contract_checks(1, 13, 10, 100, detail, "BTC_USDT")
    assert vol == 10
    vol2, N2, req2 = _apply_contract_checks(1, 7, 10, 100, detail, "BTC_USDT")
    assert vol2 == 0
