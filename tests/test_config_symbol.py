import importlib
import scalp.bot_config as bc


def test_symbol_defaults_to_zero_fee_pair(monkeypatch):
    monkeypatch.delenv("SYMBOL", raising=False)
    monkeypatch.setenv("ZERO_FEE_PAIRS", "ETH_USDT,BTC_USDT")
    importlib.reload(bc)
    try:
        assert bc.CONFIG["SYMBOL"] == "ETH_USDT"
    finally:
        monkeypatch.delenv("ZERO_FEE_PAIRS", raising=False)
        importlib.reload(bc)
