import importlib
from types import SimpleNamespace

import requests


def _fake_resp(data):
    return SimpleNamespace(json=lambda: data)


def test_fetch_zero_fee_pairs(monkeypatch, capsys):
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
    capsys.readouterr()
    pairs = bc.fetch_zero_fee_pairs_from_bitget("http://example.com")
    assert pairs == ["AAA_USDT"]
    out, _ = capsys.readouterr()
    assert "Zero-fee pairs: ['AAA_USDT']" in out


def test_fetch_pairs_with_fees(monkeypatch, capsys):
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
    capsys.readouterr()
    items = bc.fetch_pairs_with_fees_from_bitget("http://example.com")
    assert items == [
        ("AAA_USDT", 0.0, 0.0),
        ("BBB_USDT", 0.001, 0.001),
    ]
    out, _ = capsys.readouterr()
    assert "AAA_USDT: maker=0.0, taker=0.0" in out
    assert "BBB_USDT: maker=0.001, taker=0.001" in out


def test_fetch_pairs_with_fees(monkeypatch, capsys):
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
    items = bc.fetch_pairs_with_fees_from_bitget("http://example.com")
    assert items == [
        ("AAA_USDT", 0.0, 0.0),
        ("BBB_USDT", 0.001, 0.001),
    ]
    out, _ = capsys.readouterr()
    assert "AAA_USDT: maker=0.0, taker=0.0" in out
    assert "BBB_USDT: maker=0.001, taker=0.001" in out

