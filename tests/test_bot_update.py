import bot


def test_update_calls_send_selected_pairs(monkeypatch):
    calls = []

    def fake_send(client, top_n=20, tg_bot=None):
        calls.append((client, top_n, tg_bot))

    monkeypatch.setattr(bot, "send_selected_pairs", fake_send)
    bot.update("cli", top_n=5, tg_bot="tg")
    assert calls == [("cli", 5, "tg")]
