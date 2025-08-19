import importlib
from types import SimpleNamespace

import requests


def _fake_resp(data):
    return SimpleNamespace(json=lambda: data)


def test_fetch_pairs_with_fees(monkeypatch):
    def fake_get(url, timeout=5):
        return _fake_resp(
            {
                "data": [
                    {"symbol": "AAA_USDT", "takerFeeRate": 0, "makerFeeRate": 0},
                    {"symbol": "BBB_USDT", "takerFeeRate": 0.001, "makerFeeRate": 0.001},
                ]
            }
        )

    monkeypatch.setattr(requests, "get", fake_get, raising=False)
    import scalp.bot_config as bc
    importlib.reload(bc)
    items = bc.fetch_pairs_with_fees_from_mexc("http://example.com")
    assert items == [
        ("AAA_USDT", 0.0, 0.0),
        ("BBB_USDT", 0.001, 0.001),
    ]

