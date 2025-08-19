import importlib
from types import SimpleNamespace

import requests


def _fake_resp(data):
    return SimpleNamespace(json=lambda: data)


def test_symbol_defaults_without_network(monkeypatch):
    monkeypatch.delenv("SYMBOL", raising=False)
    monkeypatch.delenv("ZERO_FEE_PAIRS", raising=False)

    called = False

    def fake_get(url, timeout=5):
        nonlocal called
        called = True
        return _fake_resp({"data": []})

    monkeypatch.setattr(requests, "get", fake_get, raising=False)
    import scalp.bot_config as bc
    importlib.reload(bc)
    assert bc.CONFIG["SYMBOL"] == "BTC_USDT"
    assert called is False


def test_zero_fee_pairs_excludes_btc_eth(monkeypatch):
    monkeypatch.delenv("ZERO_FEE_PAIRS", raising=False)

    def fake_get(url, timeout=5):
        return _fake_resp(
            {
                "data": [
                    {"symbol": "BTC_USDT", "takerFeeRate": 0, "makerFeeRate": 0},
                    {"symbol": "ETH_USDT", "takerFeeRate": 0, "makerFeeRate": 0},
                    {"symbol": "DOGE_USDT", "takerFeeRate": 0, "makerFeeRate": 0},
                ]
            }
        )

    monkeypatch.setattr(requests, "get", fake_get, raising=False)
    import scalp.bot_config as bc
    importlib.reload(bc)
    assert bc.get_zero_fee_pairs() == ["DOGE_USDT"]
