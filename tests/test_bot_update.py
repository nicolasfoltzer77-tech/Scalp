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
    assert "Listing ok" in caplog.text


def test_update_survives_errors(monkeypatch, caplog):
    """``update`` should never raise even if pair selection fails."""

    def boom(client, top_n=40):  # pragma: no cover - simulated failure
        raise RuntimeError("network down")

    monkeypatch.setattr(bot, "send_selected_pairs", boom)
    with caplog.at_level(logging.INFO):
        payload = bot.update("cli", top_n=5)

    # The function returns an empty payload and logs the error, but still logs
    # the "Listing ok" acknowledgement so callers can proceed.
    assert payload == {}
    assert "network down" in caplog.text
    assert "Listing ok" in caplog.text

