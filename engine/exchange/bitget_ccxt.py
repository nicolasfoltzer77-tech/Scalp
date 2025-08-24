from __future__ import annotations
import asyncio
from typing import Any, List, Sequence

class BitgetExchange:
    """Wrapper CCXT async. Installe `ccxt` pour l'utiliser, sinon bot tombera sur REST."""
    def __init__(self, api_key: str, secret: str, password: str, data_dir: str):
        try:
            import ccxt.async_support as ccxt  # type: ignore
        except Exception as e:  # ccxt non installé
            raise RuntimeError(f"ccxt non disponible: {e}")
        self._ccxt = ccxt.bitget({"apiKey": api_key, "secret": secret, "password": password})
        self.data_dir = data_dir

    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 150) -> List[List[float]]:
        return await self._ccxt.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

    async def close(self) -> None:
        try:
            await self._ccxt.close()
        except Exception:
            pass