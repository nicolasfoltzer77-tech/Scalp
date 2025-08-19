import bot


def test_update_displays_pairs(monkeypatch, capsys):
    def fake_send(client, top_n=20, tg_bot=None):
        assert (client, top_n, tg_bot) == ("cli", 5, "tg")
        return {"green": "BTC", "orange": "ETH", "red": "XRP"}

    monkeypatch.setattr(bot, "send_selected_pairs", fake_send)
    bot.update("cli", top_n=5, tg_bot="tg")
    out = capsys.readouterr().out
    assert "BTC" in out and "ETH" in out and "XRP" in out
