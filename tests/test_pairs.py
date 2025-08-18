import bot


def test_send_selected_pairs(monkeypatch):
    sent = {}

    def fake_notify(event, payload=None):
        sent["event"] = event
        sent["payload"] = payload

    monkeypatch.setattr(bot, "notify", fake_notify)
    monkeypatch.setattr(
        bot,
        "filter_trade_pairs",
        lambda client, top_n=60: [
            {"symbol": "WIFUSDT", "volume": 10},
            {"symbol": "WIFUSDT", "volume": 9},
            {"symbol": "BTCUSD", "volume": 8},
            {"symbol": "BTCUSDT", "volume": 7},
            {"symbol": "DOGEUSDT", "volume": 6},
        ],
    )

    bot.send_selected_pairs(object(), top_n=3)

    assert sent["event"] == "pair_list"
    assert sent["payload"]["pairs"] == "WIF, BTC, DOGE"

