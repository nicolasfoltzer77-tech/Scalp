import importlib
from types import SimpleNamespace

import requests


def _fake_resp(data):
    return SimpleNamespace(json=lambda: data)


def test_fetch_zero_fee_pairs(monkeypatch):
    def fake_get(url, timeout=5):
        return _fake_resp(
            {
                "data": [
                    {"symbol": "AAA_USDT", "takerFeeRate": 0, "makerFeeRate": 0},
                    {"symbol": "BBB_USDT", "takerFeeRate": 0.001, "makerFeeRate": 0.001},
                    {"symbol": "BTC_USDT", "takerFeeRate": 0, "makerFeeRate": 0},
                ]
            }
        )

    monkeypatch.setattr(requests, "get", fake_get, raising=False)
    import scalp.bot_config as bc
    importlib.reload(bc)
    pairs = bc.fetch_zero_fee_pairs_from_mexc("http://example.com")
    assert pairs == ["AAA_USDT"]

