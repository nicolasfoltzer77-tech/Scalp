import json
import hmac
import hashlib
import base64
import pytest
import bot
from bot import BitgetFuturesClient


@pytest.fixture(autouse=True)
def no_log_event(monkeypatch):
    monkeypatch.setattr(bot, "log_event", lambda *a, **k: None)


def test_private_request_get_signature(monkeypatch):
    client = BitgetFuturesClient("key", "secret", "https://test")
    monkeypatch.setattr(BitgetFuturesClient, "_ms", staticmethod(lambda: 1000))

    called = {}

    def fake_request(method, url, headers=None, timeout=None):
        called["method"] = method
        called["url"] = url
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
    prehash = f"1000GET/api/test?{qs}"
    expected = base64.b64encode(
        hmac.new(b"secret", prehash.encode(), hashlib.sha256).digest()
    ).decode()
    assert called["headers"]["ACCESS-SIGN"] == expected
    assert called["headers"]["ACCESS-KEY"] == "key"
    assert called["headers"]["ACCESS-TIMESTAMP"] == "1000"
    assert called["headers"]["ACCESS-RECV-WINDOW"] == "30"
    assert called["url"] == "https://test/api/test?a=1&b=2"


def test_private_request_post_signature(monkeypatch):
    client = BitgetFuturesClient("key", "secret", "https://test")
    monkeypatch.setattr(BitgetFuturesClient, "_ms", staticmethod(lambda: 1000))

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
    prehash = f"1000POST/api/test{body}"
    expected = base64.b64encode(
        hmac.new(b"secret", prehash.encode(), hashlib.sha256).digest()
    ).decode()
    assert called["headers"]["ACCESS-SIGN"] == expected
    assert called["headers"]["ACCESS-KEY"] == "key"
    assert called["headers"]["ACCESS-TIMESTAMP"] == "1000"
    assert called["headers"]["ACCESS-RECV-WINDOW"] == "30"
    assert called["data"].decode("utf-8") == body
    assert called["url"] == "https://test/api/test"


def test_private_request_http_error(monkeypatch):
    client = BitgetFuturesClient("key", "secret", "https://test")
    monkeypatch.setattr(BitgetFuturesClient, "_ms", staticmethod(lambda: 1000))

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
    client = BitgetFuturesClient("key", "secret", "https://test", paper_trade=True)
    assets = client.get_assets()
    assert assets["success"] is True
    usdt = next((row for row in assets.get("data", []) if row.get("currency") == "USDT"), None)
    assert usdt and usdt["equity"] == 100.0


def test_http_client_context_manager(monkeypatch):
    import sys
    import importlib
    sys.modules.pop('requests', None)
    real_requests = importlib.import_module('requests')
    sys.modules['requests'] = real_requests
    import scalp.client as http_client
    importlib.reload(http_client)

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


def test_get_kline_query_params(monkeypatch):
    """Ensure ``get_kline`` hits the correct endpoint and passes symbol as a
    query parameter. The previous implementation embedded the symbol in the
    path which resulted in a 404 from Bitget."""

    client = BitgetFuturesClient("key", "secret", "https://test")

    called = {}

    def fake_get(url, params=None, timeout=None):
        called["url"] = url
        called["params"] = params

        class Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"data": []}

        return Resp()

    # Some tests replace ``bot.requests`` with a lightweight namespace that
    # doesn't define ``get``. ``raising=False`` ensures the attribute is added
    # even if missing so we can observe the call.
    monkeypatch.setattr(bot.requests, "get", fake_get, raising=False)

    client.get_kline("BTC_USDT", interval="Min1")

    assert called["url"].endswith("/api/v2/mix/market/candles")
    assert called["params"] == {
        "symbol": "BTCUSDT",
        "productType": "USDT-FUTURES",
        "granularity": "1m",
    }


def test_get_open_orders_endpoint(monkeypatch):
    client = BitgetFuturesClient("key", "secret", "https://test", paper_trade=False)

    called = {}

    def fake_private(self, method, path, params=None, body=None):
        called["method"] = method
        called["path"] = path
        called["params"] = params
        return {"success": True}

    monkeypatch.setattr(BitgetFuturesClient, "_private_request", fake_private)

    client.get_open_orders("BTCUSDT_UMCBL")

    assert called["path"] == "/api/v2/mix/order/orders-pending"
    assert called["params"] == {
        "productType": "USDT-FUTURES",
        "symbol": "BTCUSDT",
    }


def test_product_type_alias():
    client = BitgetFuturesClient("key", "secret", "https://test", product_type="umcbl")
    assert client.product_type == "USDT-FUTURES"


def test_get_contract_detail_endpoint(monkeypatch):
    client = BitgetFuturesClient("key", "secret", "https://test")

    called = {}

    def fake_get(url, params=None, timeout=None):
        called["url"] = url
        called["params"] = params

        class Resp:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {"data": []}

        return Resp()

    monkeypatch.setattr(bot.requests, "get", fake_get, raising=False)

    client.get_contract_detail("BTCUSDT_UMCBL")

    assert called["url"].endswith("/api/v2/mix/market/contracts")
    assert called["params"] == {
        "productType": "USDT-FUTURES",
        "symbol": "BTCUSDT",
    }


def test_cancel_all_endpoint(monkeypatch):
    client = BitgetFuturesClient("key", "secret", "https://test", paper_trade=False)

    called = {}

    def fake_private(self, method, path, params=None, body=None):
        called["method"] = method
        called["path"] = path
        called["params"] = params
        called["body"] = body
        return {"success": True}

    monkeypatch.setattr(BitgetFuturesClient, "_private_request", fake_private)

    client.cancel_all("BTCUSDT_UMCBL", margin_coin="USDT")

    assert called["method"] == "POST"
    assert called["path"] == "/api/v2/mix/order/cancel-all-orders"
    assert called["params"] == {
        "productType": "USDT-FUTURES",
        "symbol": "BTCUSDT",
        "marginCoin": "USDT",
    }
    assert called["body"] is None


def test_get_open_orders_paper_trade(monkeypatch):
    client = BitgetFuturesClient("key", "secret", "https://test", paper_trade=True)

    called = {"count": 0}

    def fake_private(*a, **k):
        called["count"] += 1
        return {"success": True}

    monkeypatch.setattr(BitgetFuturesClient, "_private_request", fake_private)

    resp = client.get_open_orders("BTCUSDT_UMCBL")

    assert resp["success"] is True
    assert resp["data"] == []
    assert called["count"] == 0


def test_cancel_all_paper_trade(monkeypatch):
    client = BitgetFuturesClient("key", "secret", "https://test", paper_trade=True)

    called = {"count": 0}

    def fake_private(*a, **k):
        called["count"] += 1
        return {"success": True}

    monkeypatch.setattr(BitgetFuturesClient, "_private_request", fake_private)

    resp = client.cancel_all("BTCUSDT_UMCBL", margin_coin="USDT")

    assert resp["success"] is True
    assert called["count"] == 0


def test_get_kline_transforms_data(monkeypatch):
    client = BitgetFuturesClient("key", "secret", "https://test")

    def fake_get(url, params=None, timeout=None):
        class Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "data": [
                        ["1", "2", "3", "1", "2", "10", "20"],
                        ["2", "3", "4", "2", "3", "11", "21"],
                    ]
                }

        return Resp()

    monkeypatch.setattr(bot.requests, "get", fake_get, raising=False)

    data = client.get_kline("BTC_USDT", interval="1m")
    kdata = data["data"]
    assert kdata["open"] == [2.0, 3.0]
    assert kdata["high"] == [3.0, 4.0]
    assert kdata["low"] == [1.0, 2.0]
    assert kdata["close"] == [2.0, 3.0]
    assert kdata["volume"] == [10.0, 11.0]
    assert kdata["quoteVolume"] == [20.0, 21.0]
