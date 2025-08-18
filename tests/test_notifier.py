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



def test_notify_posts_both(monkeypatch):
    calls = []

    def fake_post(url, json=None, timeout=5):
        calls.append({"url": url, "json": json, "timeout": timeout})

    monkeypatch.setenv("NOTIFY_URL", "http://example.com")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    monkeypatch.setattr(notifier.requests, "post", fake_post)

    notifier.notify("evt", {"bar": 2})

    assert len(calls) == 2
    assert calls[0]["url"] == "http://example.com"
    assert calls[1]["url"] == "https://api.telegram.org/botabc/sendMessage"


def test_format_text_open_position():
    payload = {
        "side": "long",
        "symbol": "BTCUSDT",
        "vol": 1,
        "leverage": 10,

        "tp_usd": 5,
        "sl_usd": 2,
        "hold": "2h",
    }
    text = notifier._format_text("position_opened", payload)
    lines = text.splitlines()
    assert lines[0] == "Ouvre long BTC"
    assert lines[1] == "Position: 1"
    assert lines[2] == "Levier: x10"
    assert "TP: +5 USDT" in lines
    assert "SL: -2 USDT" in lines
    assert any("Durée prévue: 2h" in l for l in lines)


def test_format_text_closed_position():
    payload = {
        "side": "short",
        "symbol": "ETHUSDT",
        "vol": 2,
        "leverage": 5,
        "pnl_usd": 12,
        "pnl_pct": 3,
        "duration": "1h",
    }
    text = notifier._format_text("position_closed", payload)
    lines = text.splitlines()
    assert lines[0] == "Ferme short ETH"
    assert lines[1] == "Position: 2"
    assert lines[2] == "Levier: x5"
    assert any("PnL: 12 USDT (3%)" in l for l in lines)
    assert any("Durée: 1h" in l for l in lines)

