import importlib
from types import SimpleNamespace

import requests


def _fake_resp(data):
    return SimpleNamespace(json=lambda: data)


def test_symbol_defaults_to_first_pair(monkeypatch):
    monkeypatch.delenv("SYMBOL", raising=False)
    monkeypatch.delenv("PAIRS", raising=False)

    def fake_get(url, timeout=5):
        return _fake_resp(
            {
                "data": [
                    {"symbol": "WIF_USDT", "takerFeeRate": 0, "makerFeeRate": 0},
                    {"symbol": "DOGE_USDT", "takerFeeRate": 0, "makerFeeRate": 0},
                ]
            }
        )

    monkeypatch.setattr(requests, "get", fake_get, raising=False)
    import scalp.bot_config as bc
    importlib.reload(bc)
    assert bc.CONFIG["SYMBOL"] == "WIF_USDT"


def test_pairs_deduplicate_and_include_btc(monkeypatch):
    monkeypatch.delenv("PAIRS", raising=False)

    def fake_get(url, timeout=5):
        return _fake_resp(
            {
                "data": [
                    {"symbol": "BTC_USDT", "takerFeeRate": 0, "makerFeeRate": 0},
                    {"symbol": "BTC_USDC", "takerFeeRate": 0, "makerFeeRate": 0},
                    {"symbol": "ETH_USDT", "takerFeeRate": 0, "makerFeeRate": 0},
                    {"symbol": "DOGE_USDT", "takerFeeRate": 0, "makerFeeRate": 0},
                    {"symbol": "DOGE_USDC", "takerFeeRate": 0, "makerFeeRate": 0},
                ]
            }
        )

    monkeypatch.setattr(requests, "get", fake_get, raising=False)
    import scalp.bot_config as bc
    importlib.reload(bc)
    assert bc.CONFIG["PAIRS"] == ["BTC_USDT", "ETH_USDT", "DOGE_USDT"]
