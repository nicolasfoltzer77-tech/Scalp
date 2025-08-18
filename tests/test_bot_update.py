import bot


def test_update_calls_send_selected_pairs(monkeypatch):
    calls = []

    def fake_send(client, top_n=20):
        calls.append((client, top_n))

    monkeypatch.setattr(bot, "send_selected_pairs", fake_send)
    bot.update("cli", top_n=5)
    assert calls == [("cli", 5)]
