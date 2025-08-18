import bot


def test_send_selected_pairs(monkeypatch):
    sent = {}

    def fake_notify(event, payload=None):
        sent["event"] = event
        sent["payload"] = payload

    monkeypatch.setattr(bot, "notify", fake_notify)
    monkeypatch.setattr(
        bot,
        "select_top_pairs",
        lambda client, top_n=20: [
            {"symbol": "WIFUSDT"},
            {"symbol": "WIFUSDT"},
            {"symbol": "BTCUSDT"},
        ],
    )

    bot.send_selected_pairs(object(), top_n=3)

    assert sent["event"] == "pair_list"
    assert sent["payload"]["pairs"] == "WIF, BTC"

