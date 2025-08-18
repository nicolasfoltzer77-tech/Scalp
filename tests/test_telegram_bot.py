from scalp.telegram_bot import TelegramBot


class DummyClient:

    def __init__(self):
        self.closed = []
        self.closed_all = False


    def get_assets(self):
        return {"data": [{"currency": "USDT", "equity": 123.45}]}

    def get_positions(self):
        return {
            "data": [
                {
                    "symbol": "BTC_USDT",
                    "side": "long",
                    "vol": 2,
                    "pnl_usd": 1.0,
                    "pnl_pct": 5.0,
                }
            ]
        }

    def close_position(self, sym):
        self.closed.append(sym)

    def close_all_positions(self):
        self.closed_all = True



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
    assert "BTC" in resp
    assert "PnL" in resp


def test_handle_positions_zero_pnl():
    bot = make_bot()

    def zero_positions():
        return {
            "data": [
                {
                    "symbol": "BTC_USDT",
                    "side": "long",
                    "vol": 1,
                    "pnl_usd": 0.0,
                    "pnl_pct": 0.0,
                }
            ]
        }

    bot.client.get_positions = zero_positions
    resp, _ = bot.handle_callback("positions", 0.0)
    assert "PnL: 0.0 USDT" in resp



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



def test_stop_menu_and_actions():
    bot = make_bot()
    resp, kb = bot.handle_callback("stop", 0.0)
    assert any(btn["callback_data"] == "stop_BTC" for row in kb for btn in row)
    assert any(btn["callback_data"] == "stop_all" for row in kb for btn in row)
    resp, _ = bot.handle_callback("stop_BTC", 0.0)
    assert "fermée" in resp.lower()
    assert bot.client.closed == ["BTC"]
    resp, _ = bot.handle_callback("stop_all", 0.0)
    assert bot.client.closed_all is True


def test_handle_unknown():
    bot = make_bot()
    resp, kb = bot.handle_callback("foobar", 0.0)
    assert resp is None
    assert kb is None


def test_analysis_button_present():
    bot = make_bot()
    assert any(
        btn["callback_data"] == "analysis" for row in bot.main_keyboard for btn in row
    )


def test_handle_analysis():
    bot = make_bot(
        {
            "ANALYSIS_PAIRS": [
                {"symbol": "BTC", "status": "ready"},
                {"symbol": "ETH", "status": "lt10"},
                {"symbol": "XRP", "status": "gt10"},
            ]
        }
    )
    resp, kb = bot.handle_callback("analysis", 0.0)
    assert "BTC" in resp and "prêt à lancer" in resp
    assert "ETH" in resp and "moins de 10 min" in resp
    assert "XRP" in resp and "plus de 10 min" in resp
    assert kb == bot.analysis_keyboard

