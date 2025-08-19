import json
import hmac
import hashlib
import pytest
import bot
from bot import MexcFuturesClient
import sys
import importlib

sys.modules.pop("requests", None)
real_requests = importlib.import_module("requests")
sys.modules["requests"] = real_requests
import scalp.client as http_client


@pytest.fixture(autouse=True)
def no_log_event(monkeypatch):
    monkeypatch.setattr(bot, "log_event", lambda *a, **k: None)


def test_private_request_get_signature(monkeypatch):
    client = MexcFuturesClient("key", "secret", "https://test")
    monkeypatch.setattr(MexcFuturesClient, "_ms", staticmethod(lambda: 1000))

    called = {}

    def fake_request(method, url, params=None, headers=None, timeout=None):
        called["method"] = method
        called["url"] = url
        called["params"] = params
        called["headers"] = headers

        class Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"success": True}

        return Resp()

    monkeypatch.setattr(bot.requests, "request", fake_request)

    resp = client._private_request("GET", "/api/test", params={"b": "2", "a": "1"})
    assert resp["success"] is True
    qs = "a=1&b=2"
    expected = hmac.new(b"secret", f"key1000{qs}".encode(), hashlib.sha256).hexdigest()
    assert called["headers"]["Signature"] == expected
    assert called["headers"]["ApiKey"] == "key"
    assert called["params"] == {"b": "2", "a": "1"}


def test_private_request_post_signature(monkeypatch):
    client = MexcFuturesClient("key", "secret", "https://test")
    monkeypatch.setattr(MexcFuturesClient, "_ms", staticmethod(lambda: 1000))

    called = {}

    def fake_post(url, data=None, headers=None, timeout=None):
        called["url"] = url
        called["data"] = data
        called["headers"] = headers

        class Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"success": True}

        return Resp()

    monkeypatch.setattr(bot.requests, "post", fake_post)

    resp = client._private_request("POST", "/api/test", body={"a": 1, "b": 2})
    assert resp["success"] is True
    body = json.dumps({"a": 1, "b": 2}, separators=(",", ":"), ensure_ascii=False)
    expected = hmac.new(b"secret", f"key1000{body}".encode(), hashlib.sha256).hexdigest()
    assert called["headers"]["Signature"] == expected
    assert called["headers"]["ApiKey"] == "key"
    assert called["data"].decode("utf-8") == body


def test_private_request_http_error(monkeypatch):
    client = MexcFuturesClient("key", "secret", "https://test")
    monkeypatch.setattr(MexcFuturesClient, "_ms", staticmethod(lambda: 1000))

    class Resp:
        status_code = 418

        def raise_for_status(self):
            raise bot.requests.HTTPError("teapot")

        def json(self):
            return {"unused": True}

    monkeypatch.setattr(bot.requests, "request", lambda *a, **k: Resp())

    resp = client._private_request("GET", "/api/test")
    assert resp["success"] is False
    assert resp["status_code"] == 418
    assert "teapot" in resp["error"]


def test_get_assets_paper_trade():
    client = MexcFuturesClient("key", "secret", "https://test", paper_trade=True)
    assets = client.get_assets()
    assert assets["success"] is True
    usdt = next((row for row in assets.get("data", []) if row.get("currency") == "USDT"), None)
    assert usdt and usdt["equity"] == 100.0


def test_http_client_context_manager(monkeypatch):
    closed = {"count": 0}

    class DummySession:
        def mount(self, *a, **k):
            pass

        def request(self, *a, **k):
            class Resp:
                def raise_for_status(self):
                    pass

                def json(self):
                    return {}

                text = "{}"

            return Resp()

        def close(self):
            closed["count"] += 1

    monkeypatch.setattr(http_client.requests, "Session", lambda: DummySession())

    http = http_client.HttpClient("http://example.com")
    http.close()
    assert closed["count"] == 1

    closed["count"] = 0
    with http_client.HttpClient("http://example.com") as hc:
        hc.request("GET", "/")
    assert closed["count"] == 1
