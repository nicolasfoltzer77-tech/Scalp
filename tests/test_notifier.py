import scalp.notifier as notifier


def test_notify_skips_without_url(monkeypatch):
    called = False

    def fake_post(url, json=None, timeout=5):  # pragma: no cover - fallback
        nonlocal called
        called = True

    monkeypatch.delenv("NOTIFY_URL", raising=False)
    monkeypatch.setattr(notifier.requests, "post", fake_post)
    notifier.notify("test", {"foo": 1})
    assert called is False


def test_notify_posts(monkeypatch):
    payload = {}

    def fake_post(url, json=None, timeout=5):
        payload["url"] = url
        payload["json"] = json
        payload["timeout"] = timeout

    monkeypatch.setenv("NOTIFY_URL", "http://example.com")
    monkeypatch.setattr(notifier.requests, "post", fake_post)
    notifier.notify("evt", {"bar": 2})
    assert payload["url"] == "http://example.com"
    assert payload["json"]["event"] == "evt"
    assert payload["json"]["bar"] == 2
