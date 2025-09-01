# engine/exchanges/ccxt_bitget.py
from __future__ import annotations

import os
import ccxt


def resolve_ccxt_symbol(sym: str) -> str:
    """
    Force un symbole au format CCXT pour Bitget Futures USDT.
    Exemple: "XRPUSDT" -> "XRP/USDT:USDT"
    """
    s = sym.upper().replace("-", "").replace("/", "")
    if not s.endswith("USDT"):
        s += "USDT"
    return s.replace("USDT", "/USDT:USDT")


def make_exchange_from_env() -> ccxt.bitget:
    """
    Initialise CCXT Bitget avec API key/secret depuis env :
      BITGET_API_KEY, BITGET_API_SECRET, BITGET_API_PASSWORD
    Et active le sandbox si BITGET_SANDBOX=1
    """
    api_key = os.getenv("BITGET_API_KEY")
    api_secret = os.getenv("BITGET_API_SECRET")
    api_pass = os.getenv("BITGET_API_PASSWORD")
    sandbox = os.getenv("BITGET_SANDBOX", "0") == "1"

    ex = ccxt.bitget({
        "apiKey": api_key,
        "secret": api_secret,
        "password": api_pass,
        "enableRateLimit": True,
    })

    if sandbox:
        ex.set_sandbox_mode(True)

    # précharger les markets
    ex.load_markets()
    return ex


class CcxtBitgetAdapter:
    """
    Adapter simple pour homogénéiser l'accès aux appels CCXT.
    """

    def __init__(self, exchange: ccxt.bitget) -> None:
        self.exchange = exchange

    def market(self, sym: str) -> dict:
        return self.exchange.market(resolve_ccxt_symbol(sym))

    def fetch_ticker(self, sym: str) -> dict:
        return self.exchange.fetch_ticker(resolve_ccxt_symbol(sym))

    def create_order(self, symbol: str, side: str, type_: str, amount: float, price: float | None, params=None) -> dict:
        return self.exchange.create_order(
            resolve_ccxt_symbol(symbol),
            type_,
            side,
            amount,
            price,
            params or {},
        )
