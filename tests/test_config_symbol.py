import importlib
import scalp.bot_config as bc


def test_symbol_defaults_to_zero_fee_pair(monkeypatch):
    monkeypatch.delenv("SYMBOL", raising=False)
    monkeypatch.setenv("ZERO_FEE_PAIRS", "WIF_USDT,DOGE_USDT")
    importlib.reload(bc)
    try:
        assert bc.CONFIG["SYMBOL"] == "WIF_USDT"
    finally:
        monkeypatch.delenv("ZERO_FEE_PAIRS", raising=False)
        importlib.reload(bc)


def test_zero_fee_pairs_excludes_btc_eth(monkeypatch):
    monkeypatch.setenv("ZERO_FEE_PAIRS", "BTC_USDT,ETH_USDT,DOGE_USDT")
    importlib.reload(bc)
    try:
        assert bc.CONFIG["ZERO_FEE_PAIRS"] == ["DOGE_USDT"]
    finally:
        monkeypatch.delenv("ZERO_FEE_PAIRS", raising=False)
        importlib.reload(bc)
