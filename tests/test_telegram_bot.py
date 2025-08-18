from scalp.telegram_bot import TelegramBot


class DummyClient:
    def get_assets(self):
        return {"data": [{"currency": "USDT", "equity": 123.45}]}

    def get_positions(self):
        return {"data": [{"symbol": "BTC_USDT", "side": "long", "vol": 2}]}


def make_bot(config=None):
    cfg = {"RISK_LEVEL": 2}
    if config:
        cfg.update(config)
    return TelegramBot("t", "1", DummyClient(), cfg)


def test_handle_balance():
    bot = make_bot()
    resp, kb = bot.handle_callback("balance", 0.0)
    assert "123.45" in resp
    assert kb == bot.main_keyboard


def test_handle_positions():
    bot = make_bot()
    resp, _ = bot.handle_callback("positions", 0.0)
    assert "BTC_USDT" in resp
    assert "long" in resp


def test_handle_pnl():
    bot = make_bot()
    resp, _ = bot.handle_callback("pnl", 5.0)
    assert "5.0" in resp


def test_handle_risk_change():
    bot = make_bot()
    resp, kb = bot.handle_callback("risk3", 0.0)
    assert "3" in resp
    assert bot.config["RISK_LEVEL"] == 3
    assert kb == bot.main_keyboard


def test_risk_menu():
    bot = make_bot()
    resp, kb = bot.handle_callback("risk", 0.0)
    assert "risque" in resp.lower()
    assert kb == bot.risk_keyboard


def test_handle_unknown():
    bot = make_bot()
    resp, kb = bot.handle_callback("foobar", 0.0)
    assert resp is None
    assert kb is None
