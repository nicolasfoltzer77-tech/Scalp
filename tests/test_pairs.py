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
        lambda client, top_n=20: [{"symbol": "BTCUSDT"}, {"symbol": "ETHUSDT"}],
    )

    bot.send_selected_pairs(object(), top_n=2)

    assert sent["event"] == "pair_list"
    assert "BTCUSDT" in sent["payload"]["pairs"]
    assert "ETHUSDT" in sent["payload"]["pairs"]

