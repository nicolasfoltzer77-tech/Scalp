import importlib

def test_symbol_defaults_without_env(monkeypatch):
    monkeypatch.delenv("SYMBOL", raising=False)
    import scalp.bot_config as bc
    importlib.reload(bc)
    assert bc.CONFIG["SYMBOL"] == "BTC_USDT"
