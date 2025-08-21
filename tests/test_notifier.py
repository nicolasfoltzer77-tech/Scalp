import scalp.notifier as notifier


def test_notify_skips_without_targets(monkeypatch):
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


def test_notify_posts_http(monkeypatch):
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
    payload = {}

    def fake_post(url, json=None, timeout=5):
        payload["url"] = url
        payload["json"] = json
        payload["timeout"] = timeout

    monkeypatch.delenv("NOTIFY_URL", raising=False)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    monkeypatch.setattr(notifier.requests, "post", fake_post)

    notifier.notify("evt", {"bar": 2})

    assert payload["url"] == "https://api.telegram.org/botabc/sendMessage"
    assert payload["json"]["chat_id"] == "123"
    assert "evt" in payload["json"]["text"]


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
    urls = {c["url"] for c in calls}
    assert "http://example.com" in urls
    assert "https://api.telegram.org/botabc/sendMessage" in urls


def test_notify_skips_telegram_for_pair_list(monkeypatch):
    calls = []

    def fake_post(url, json=None, timeout=5):
        calls.append(url)

    monkeypatch.setenv("NOTIFY_URL", "http://example.com")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    monkeypatch.setattr(notifier.requests, "post", fake_post)

    notifier.notify("pair_list", {"pairs": "BTC"})

    # Only the generic webhook should be called, not Telegram
    assert calls == ["http://example.com"]


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

    assert lines[0] == "Ouvre long 📈 BTC"
    assert lines[1] == "Position: 1"
    assert lines[2] == "Levier: x10"
    assert "TP: +5 USDT" in lines
    assert "SL: -2 USDT" in lines
    assert any("Durée prévue: 2h" in line for line in lines)


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
    assert lines[0] == "Ferme short 📉 ETH ✅🎯"
    assert lines[1] == "Position: 2"
    assert lines[2] == "Levier: x5"
    assert any("PnL: 12 USDT (3.00%)" in line for line in lines)
    assert any("Durée: 1h" in line for line in lines)


def test_format_text_pair_list_and_start():
    assert notifier._format_text("bot_started") == "🤖 Bot démarré"
    text = notifier._format_text(
        "pair_list", {"green": "AAA", "orange": "BBB", "red": "CCC"}
    )
    assert text == "Listing :\n🟢 AAA\n🟠 BBB\n🔴 CCC"


def test_format_pair_list_helper():
    payload = {"green": "AAA", "orange": "BBB", "red": "CCC"}
    text = notifier._format_pair_list(payload)
    assert text == "Listing :\n🟢 AAA\n🟠 BBB\n🔴 CCC"


def test_format_position_event_helper():
    payload = {
        "side": "long",
        "symbol": "BTCUSDT",
        "vol": 1,
        "leverage": 10,
        "tp_pct": 5,
        "sl_pct": 2,
    }
    text = notifier._format_position_event("position_opened", payload)
    assert text.splitlines()[0] == "Ouvre long 📈 BTC"


