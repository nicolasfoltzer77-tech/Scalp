# scalper/exchange/bitget_ccxt.py
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import List, Any

import csv

# ccxt async
try:
    import ccxt.async_support as ccxt  # type: ignore
except Exception:  # pragma: no cover
    ccxt = None  # sera installé par bot.py (ensure_ccxt)

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True, parents=True)


def _csv_path(symbol: str, timeframe: str) -> Path:
    return DATA_DIR / f"{symbol}-{timeframe}.csv"


def _read_csv_ohlcv(path: Path, limit: int) -> List[List[Any]]:
    if not path.exists():
        return []
    out: List[List[Any]] = []
    with path.open("r", newline="") as f:
        r = csv.reader(f)
        header = next(r, None)  # timestamp,open,high,low,close,volume
        for row in r:
            try:
                ts = int(row[0])
                o = float(row[1]); h = float(row[2]); l = float(row[3]); c = float(row[4]); v = float(row[5])
                out.append([ts, o, h, l, c, v])
            except Exception:
                continue
    if limit and len(out) > limit:
        out = out[-limit:]
    return out


class CcxtBitget:
    """
    Exchange minimal pour l'orchestrateur :
      - fetch_ohlcv via CCXT Bitget (async)
      - fallback CSV local si CCXT échoue
    """

    def __init__(self) -> None:
        if ccxt is None:
            raise RuntimeError("ccxt non disponible (installé au démarrage dans bot.py).")
        api_key = os.getenv("BITGET_API_KEY") or None
        secret = os.getenv("BITGET_API_SECRET") or None
        password = os.getenv("BITGET_API_PASSPHRASE") or os.getenv("BITGET_API_PASSWORD") or None

        opts = {
            "enableRateLimit": True,
            "options": {"defaultType": "swap"},   # ou 'spot' selon ton besoin (le backtest lit juste OHLCV)
        }
        if api_key and secret:
            opts["apiKey"] = api_key
            opts["secret"] = secret
            if password:
                opts["password"] = password

        self._ex = ccxt.bitget(opts)

    async def fetch_ohlcv(self, symbol: str, timeframe: str = "5m", limit: int = 1000) -> List[List[Any]]:
        """
        Retourne des bougies au format [[ts, open, high, low, close, volume], ...]
        - Essaie CCXT en premier
        - En cas d'échec, fallback CSV: data/<SYMBOL>-<TF>.csv
        """
        # 1) tentative CCXT
        try:
            data = await self._ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            # ccxt renvoie déjà [ts, o, h, l, c, v] (ts en ms)
            return data
        except Exception:
            # 2) fallback CSV local
            path = _csv_path(symbol, timeframe)
            csv_data = _read_csv_ohlcv(path, limit)
            if csv_data:
                return csv_data
            raise  # remonter l'erreur si pas de CSV

    async def close(self) -> None:
        try:
            await self._ex.close()
        except Exception:
            pass


async def create_exchange() -> CcxtBitget:
    # rien de spécial ici mais on garde async pour symétrie
    return CcxtBitget()