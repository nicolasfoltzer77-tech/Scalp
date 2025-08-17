import scalp.notifier as notifier


def test_notify_skips_without_url(monkeypatch):
    called = False

    def fake_post(url, json=None, timeout=5):  # pragma: no cover - fallback
        nonlocal called
        called = True

    monkeypatch.delenv("NOTIFY_URL", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setattr(notifier.requests, "post", fake_post)
    notifier.notify("test", {"foo": 1})
    assert called is False


def test_notify_posts(monkeypatch):
    payload = {}

    def fake_post(url, json=None, timeout=5):
        payload["url"] = url
        payload["json"] = json
        payload["timeout"] = timeout

    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setenv("NOTIFY_URL", "http://example.com")
    monkeypatch.setattr(notifier.requests, "post", fake_post)
    notifier.notify("evt", {"bar": 2})
    assert payload["url"] == "http://example.com"
    assert payload["json"]["event"] == "evt"
    assert payload["json"]["bar"] == 2


def test_notify_posts_telegram(monkeypatch):
    calls = []

    def fake_post(url, json=None, timeout=5):
        calls.append({"url": url, "json": json, "timeout": timeout})

    monkeypatch.delenv("NOTIFY_URL", raising=False)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    monkeypatch.setattr(notifier.requests, "post", fake_post)

    notifier.notify("evt", {"bar": 2})

    assert len(calls) == 1
    assert calls[0]["url"] == "https://api.telegram.org/botabc/sendMessage"
    assert calls[0]["json"]["chat_id"] == "123"
    assert calls[0]["json"]["text"].startswith("evt")
    assert "bar" in calls[0]["json"]["text"]
