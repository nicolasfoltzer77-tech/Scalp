import logging
import bot


def test_update_displays_pairs(monkeypatch, caplog):
    def fake_send(client, top_n=20, tg_bot=None):
        assert (client, top_n, tg_bot) == ("cli", 5, "tg")
        return {"green": "BTC", "orange": "ETH", "red": "XRP"}

    monkeypatch.setattr(bot, "send_selected_pairs", fake_send)
    with caplog.at_level(logging.INFO):
        payload = bot.update("cli", top_n=5, tg_bot="tg")
    assert payload["green"] == "BTC"
    assert "BTC" in caplog.text and "ETH" in caplog.text and "XRP" in caplog.text

