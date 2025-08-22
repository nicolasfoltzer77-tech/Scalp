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
        "symbol": "BTCUSDT",
        "side": "short",
        "price": 18350,
        "vol": 37,
        "contract_size": 1,
        "notional_usdt": 120.5,
        "leverage": 5,
        "required_margin_usdt": 25.3,
        "available_usdt": 134,
        "risk_level_user": 3,
        "signal_level": 2,
        "risk_color": "🟡",
        "risk_pct_eff": 0.01,
        "fee_rate": 0.001,
    }
    text = notifier._format_text("position_opened", payload)
    lines = text.splitlines()

    assert lines[0] == "🟡 Ouvre short BTC"
    assert lines[1] == "Notional: 120.5 USDT   Levier: x5"
    assert lines[2] == "Marge estimée: 25.3 USDT (dispo: 134 USDT)"
    assert lines[3] == "Risque: lvl 2/3 (risk_pct=1.0000%)"
    assert lines[4] == "Prix: 18350   Vol: 37 (cs=1)"


def test_format_text_closed_position():
    payload = {
        "symbol": "BTCUSDT",
        "side": "short",
        "entry_price": 18350,
        "exit_price": 18328,
        "vol": 37,
        "contract_size": 1,
        "notional_entry_usdt": 120.5,
        "notional_exit_usdt": 120.3,
        "fees_usdt": 0.03,
        "pnl_usdt": 0.84,
        "pnl_pct_on_margin": 3.25,
        "leverage": 5,
        "risk_color": "🟡",
        "fee_rate": 0.001,
    }
    text = notifier._format_text("position_closed", payload)
    lines = text.splitlines()
    assert lines[0] == "Ferme short BTC 🟡"
    assert lines[1] == "PnL net: +0.84 USDT (frais: 0.03)"
    assert lines[2] == "% sur marge: 3.25%"
    assert lines[3] == "Entrée: 18350  Sortie: 18328"
    assert lines[4] == "Vol: 37  Notional: in 120.5 → out 120.3 USDT"


def test_format_text_pair_list_and_start():
    assert notifier._format_text("bot_started") == "🤖 Bot démarré"
    text = notifier._format_text(
        "pair_list", {"green": "AAA", "orange": "BBB", "red": "CCC"}
    )
    assert text == "Listing ok"


def test_format_pair_list_helper():
    payload = {"green": "AAA", "orange": "BBB", "red": "CCC"}
    text = notifier._format_pair_list(payload)
    assert text == "Listing ok"


def test_format_position_event_helper():
    payload = {
        "symbol": "BTCUSDT",
        "side": "short",
        "price": 18350,
        "vol": 37,
        "contract_size": 1,
        "notional_usdt": 120.5,
        "leverage": 5,
        "required_margin_usdt": 25.3,
        "available_usdt": 134,
        "risk_level_user": 3,
        "signal_level": 2,
        "risk_color": "🟡",
        "risk_pct_eff": 0.01,
        "fee_rate": 0.001,
    }
    text = notifier._format_position_event("position_opened", payload)
    assert text.splitlines()[0] == "🟡 Ouvre short BTC"


