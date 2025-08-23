# scalper/hooks/prewarm_cache.py
from __future__ import annotations

import os
from typing import Iterable, Dict

from scalper.services.data_cache import prewarm_csv_cache

async def prewarm_from_config(exchange, config: dict, symbols: Iterable[str], timeframe: str) -> Dict[str, str]:
    """
    Pré-chauffe le cache CSV OHLCV selon la config actuelle.
    Affiche un petit résumé.
    """
    data_dir = os.getenv("DATA_DIR", "/notebooks/data")
    print(f"[cache] prewarm -> {len(list(symbols))} symbols @ {timeframe} -> {data_dir}")
    res = await prewarm_csv_cache(exchange, symbols, timeframe)
    print(f"[cache] ready: {len(res)} csv")
    return res