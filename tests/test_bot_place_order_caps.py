import os
import sys
import types
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
sys.modules['requests'] = types.ModuleType('requests')

from bot import attempt_entry, Signal


class DummyClient:
    def __init__(self):
        self.last_order = None

    def place_order(self, *args, **kwargs):  # pragma: no cover - simple store
        self.last_order = (args, kwargs)
        return {"code": "00000"}


class DummyRisk:
    def __init__(self, pct):
        self.risk_pct = pct


def _detail():
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


def test_attempt_entry_respects_caps(monkeypatch):
    captured = {}

    def fake_notify(event, payload):
        captured[event] = payload

    monkeypatch.setattr("bot.notify", fake_notify)
    client = DummyClient()
    sig = Signal("BTC_USDT", "long", 10000, 9900, 10100, 10200, 1, score=80)
    rm = DummyRisk(0.02)
    equity = 100
    available = 2.2  # just enough for 1 contract with buffer
    params = attempt_entry(
        client,
        _detail(),
        sig,
        equity_usdt=equity,
        available_usdt=available,
        cfg={"LEVERAGE": 10},
        risk_mgr=rm,
        user_risk_level=1,
    )
    assert client.last_order is not None
    assert params["vol"] >= 1
    opened = captured["position_opened"]
    assert opened["notional_usdt"] >= 5
    assert opened["vol"] >= 1


def test_attempt_entry_insufficient_margin(monkeypatch):
    captured = {}

    def fake_notify(event, payload):
        captured[event] = payload

    monkeypatch.setattr("bot.notify", fake_notify)
    client = DummyClient()
    sig = Signal("BTC_USDT", "long", 10000, 9900, 10100, 10200, 1, score=80)
    rm = DummyRisk(0.02)
    equity = 100
    available = 1.0  # below required margin
    params = attempt_entry(
        client,
        _detail(),
        sig,
        equity_usdt=equity,
        available_usdt=available,
        cfg={"LEVERAGE": 10},
        risk_mgr=rm,
        user_risk_level=1,
    )
    assert client.last_order is None
    assert params["vol"] == 0
    assert captured["order_blocked"]["reason"].startswith("volume reduced")


def test_attempt_entry_under_min_trade(monkeypatch):
    captured = {}

    def fake_notify(event, payload):
        captured[event] = payload

    monkeypatch.setattr("bot.notify", fake_notify)
    client = DummyClient()
    sig = Signal("BTC_USDT", "long", 10000, 9900, 10100, 10200, 1, score=80)
    rm = DummyRisk(0.02)
    detail = {
        "data": [
            {
                "symbol": "BTC_USDT",
                "contractSize": 0.001,
                "volUnit": 1,
                "minVol": 1,
                "minTradeUSDT": 50,
            }
        ]
    }
    equity = 100
    available = 100
    params = attempt_entry(
        client,
        detail,
        sig,
        equity_usdt=equity,
        available_usdt=available,
        cfg={"LEVERAGE": 10},
        risk_mgr=rm,
        user_risk_level=1,
    )
    assert client.last_order is None
    assert params["vol"] == 0
    assert captured["order_blocked"]["reason"].startswith("volume reduced")
