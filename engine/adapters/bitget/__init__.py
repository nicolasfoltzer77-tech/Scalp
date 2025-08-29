from __future__ import annotations
from .ohlcv import OhlcvClient
from .trading import TradingClient

class BitgetClient(OhlcvClient, TradingClient):
    """
    Façade pour compatibilité: un seul client qui hérite des 2 côtés.
    >>> from engine.adapters.bitget import BitgetClient
    """
    def __init__(self, market: str = "umcbl"):
        OhlcvClient.__init__(self, market=market)
        TradingClient.__init__(self, market=market)

