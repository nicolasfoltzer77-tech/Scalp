import bot


def test_get_trade_pairs():
    class Client:
        def get_ticker(self, symbol=None):
            return {
                "success": True,
                "data": [
                    {"symbol": "BTC_USDT"},
                    {"symbol": "ETH_USDT"},
                ],
            }

    pairs = bot.get_trade_pairs(Client())
    assert [p["symbol"] for p in pairs] == ["BTC_USDT", "ETH_USDT"]


def test_select_top_pairs():
    class Client:
        def get_ticker(self, symbol=None):
            return {
                "success": True,
                "data": [
                    {"symbol": "A", "volume": "1"},
                    {"symbol": "B", "volume": "3"},
                    {"symbol": "C", "volume": "2"},
                ],
            }

    top = bot.select_top_pairs(Client(), top_n=2)
    assert [p["symbol"] for p in top] == ["B", "C"]


def test_find_trade_positions(monkeypatch):
    class Client:
        def __init__(self):
            self.data = {
                "AAA": {"data": {"close": [1, 2, 3]}},
                "BBB": {"data": {"close": [3, 2, 1]}},
            }

        def get_kline(self, symbol, interval="Min1"):
            return self.data[symbol]

    pairs = [
        {"symbol": "AAA", "lastPrice": "1"},
        {"symbol": "BBB", "lastPrice": "1"},
    ]

    monkeypatch.setattr(bot, "ema", lambda series, window: series)

    def fake_cross(last_fast, last_slow, prev_fast, prev_slow):
        if last_fast > prev_fast:
            return 1
        if last_fast < prev_fast:
            return -1
        return 0

    monkeypatch.setattr(bot, "cross", fake_cross)

    signals = bot.find_trade_positions(Client(), pairs, ema_fast_n=1, ema_slow_n=1)
    assert signals == [
        {"symbol": "AAA", "signal": "long", "price": 1.0},
        {"symbol": "BBB", "signal": "short", "price": 1.0},
    ]
