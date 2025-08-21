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



class DummyRiskMgr:

    def __init__(self):
        self.reset_called = False

    def reset_day(self):
        self.reset_called = True


class DummyRequests:
    def __init__(self):
        self.posts = []

    def post(self, url, json=None, timeout=5):
        self.posts.append((url, json))

    def get(self, url, params=None, timeout=5):  # pragma: no cover - unused
        return type("R", (), {"json": lambda self: {}, "raise_for_status": lambda self: None})()


def make_bot(config=None, requests_module=None):
    cfg = {"RISK_LEVEL": 2}
    if config:
        cfg.update(config)
    if requests_module is None:
        requests_module = DummyRequests()
    return TelegramBot("t", "1", DummyClient(), cfg, DummyRiskMgr(), requests_module=requests_module)


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

    resp, kb = bot.handle_callback("risk_red", 0.0)
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
    assert any(
        btn["callback_data"] == "stop_BTC_USDT" for row in kb for btn in row
    )
    assert any(btn["callback_data"] == "stop_all" for row in kb for btn in row)
    resp, _ = bot.handle_callback("stop_BTC_USDT", 0.0)
    assert "fermée" in resp.lower()
    assert bot.client.closed == ["BTC_USDT"]
    resp, _ = bot.handle_callback("stop_all", 0.0)
    assert bot.client.closed_all is True


def test_handle_unknown():
    bot = make_bot()
    resp, kb = bot.handle_callback("foobar", 0.0)
    assert resp is None
    assert kb is None


def test_reset_all():
    bot = make_bot()
    resp, kb = bot.handle_callback("reset_all", 0.0)
    assert "réinitialisés" in resp.lower()
    assert bot.risk_mgr.reset_called is True
    assert bot.client.closed_all is True
    assert kb == bot.settings_keyboard


def test_shutdown_bot():
    bot = make_bot()
    resp, kb = bot.handle_callback("shutdown", 0.0)
    assert "arrêt" in resp.lower()
    assert bot.stop_requested is True
    assert kb == bot.main_keyboard


def test_start_sends_menu():
    req = DummyRequests()
    make_bot(requests_module=req)
    assert req.posts
    text = req.posts[0][1]["text"]
    assert "Solde" in text and "PnL session" in text


def test_settings_menu_and_reset_risk():
    bot = make_bot()
    resp, kb = bot.handle_callback("settings", 0.0)
    assert "réglages" in resp.lower()
    assert kb == bot.settings_keyboard
    resp, kb = bot.handle_callback("reset_risk", 0.0)
    assert "risque" in resp.lower()
    assert bot.risk_mgr.reset_called is True
    assert kb == bot.settings_keyboard


def test_update_button(monkeypatch):
    bot = make_bot()
    called = {}

    def fake_update():
        called["called"] = True

    bot.update_pairs = fake_update
    resp, kb = bot.handle_callback("update", 0.0)
    assert called["called"] is True
    assert "mise à jour" in resp.lower()
    assert kb == bot.main_keyboard


def test_stop_no_positions():
    bot = make_bot()
    bot.client.get_positions = lambda: {"data": []}
    resp, kb = bot.handle_callback("stop", 0.0)
    assert "aucune crypto" in resp.lower()
    assert kb == bot.settings_keyboard

