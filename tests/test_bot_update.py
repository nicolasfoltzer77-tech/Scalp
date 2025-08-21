import logging
import bot


def test_update_displays_pairs(monkeypatch, caplog):
    def fake_send(client, top_n=40):
        assert (client, top_n) == ("cli", 5)
        return {"green": "BTC", "orange": "ETH", "red": "XRP"}

    monkeypatch.setattr(bot, "send_selected_pairs", fake_send)
    with caplog.at_level(logging.INFO):
        payload = bot.update("cli", top_n=5)
    assert payload["green"] == "BTC"
    assert "BTC" in caplog.text and "ETH" in caplog.text and "XRP" in caplog.text

