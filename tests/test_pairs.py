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
            {"symbol": "ETHUSDC", "volume": 5},
            {"symbol": "ETHUSDT", "volume": 4},
        ],
    )

    bot.send_selected_pairs(object(), top_n=4)

    assert sent["event"] == "pair_list"
    assert sent["payload"]["green"] == "WIF"
    assert sent["payload"]["orange"] == "BTC"
    assert sent["payload"]["red"] == "DOGE, ETH"


def test_filter_trade_pairs_all_pairs(monkeypatch):
    class DummyClient:
        def get_ticker(self):
            return {
                "data": [
                    {"symbol": "BTCUSDT", "volume": 100, "bidPrice": 1, "askPrice": 1.0001},
                    {"symbol": "ETHUSDT", "volume": 90, "bidPrice": 1, "askPrice": 1.0001},
                ]
            }

    client = DummyClient()
    res = bot.filter_trade_pairs(client, volume_min=0, max_spread_bps=10, top_n=5)
    assert [r["symbol"] for r in res] == ["BTCUSDT", "ETHUSDT"]

