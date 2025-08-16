import pathlib
import sys
import types

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
requests = types.SimpleNamespace(HTTPError=Exception, request=None, post=None, get=None)
sys.modules["requests"] = requests

import json
import hmac
import hashlib
import pytest
import bot
from bot import MexcFuturesClient


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
            raise requests.HTTPError("teapot")

        def json(self):
            return {"unused": True}

    monkeypatch.setattr(bot.requests, "request", lambda *a, **k: Resp())

    resp = client._private_request("GET", "/api/test")
    assert resp["success"] is False
    assert resp["status_code"] == 418
    assert "teapot" in resp["error"]
