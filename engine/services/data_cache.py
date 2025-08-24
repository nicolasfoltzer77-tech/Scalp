# scalper/services/data_cache.py
from __future__ import annotations

import asyncio
import csv
import os
import time
from typing import Iterable, List, Optional, Tuple, Dict

# ---------------------------------------------------------------------
# Réglages via env (valeurs sûres par défaut)
# ---------------------------------------------------------------------
DATA_DIR = os.getenv("DATA_DIR", "/notebooks/data")           # dossier PERSISTANT (hors-git)
CSV_MAX_AGE = int(os.getenv("CSV_MAX_AGE_SECONDS", "0"))      # 0 = auto (en fonction du TF)
CSV_MIN_ROWS = int(os.getenv("CSV_MIN_ROWS", "200"))          # minimum de lignes attendues
STALE_FACTOR = float(os.getenv("CSV_STALE_FACTOR", "6"))      # âge max = STALE_FACTOR * tf_sec
PREFETCH_CONC = int(os.getenv("CSV_PREFETCH_CONC", "4"))      # concurrence préchauffage

os.makedirs(DATA_DIR, exist_ok=True)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def parse_timeframe_to_seconds(tf: str) -> int:
    tf = tf.strip().lower()
    unit = tf[-1]
    try:
        n = int(tf[:-1])
    except Exception as e:
        raise ValueError(f"timeframe invalide: {tf}") from e
    if unit == "m":
        return n * 60
    if unit == "h":
        return n * 3600
    if unit == "d":
        return n * 86400
    raise ValueError(f"timeframe invalide: {tf}")


def csv_path(symbol: str, timeframe: str) -> str:
    return os.path.join(DATA_DIR, f"{symbol}-{timeframe}.csv")


def read_csv_ohlcv(path: str) -> List[Tuple[int, float, float, float, float, float]]:
    rows: List[Tuple[int, float, float, float, float, float]] = []
    if not os.path.exists(path):
        return rows
    with open(path, "r", newline="") as f:
        r = csv.reader(f)
        header = next(r, None)  # accepte avec ou sans header
        for line in r:
            if not line:
                continue
            ts, o, h, l, c, v = line[:6]
            rows.append((int(ts), float(o), float(h), float(l), float(c), float(v)))
    return rows


def write_csv_ohlcv(path: str, data: Iterable[Tuple[int, float, float, float, float, float]]) -> None:
    first = not os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if first:
            w.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for row in data:
            w.writerow(row)


def last_ts(rows: List[Tuple[int, float, float, float, float, float]]) -> Optional[int]:
    return rows[-1][0] if rows else None


# ---------------------------------------------------------------------
# Fetch CCXT paginé
# ---------------------------------------------------------------------
async def ccxt_fetch_ohlcv_all(
    exchange,
    symbol: str,
    timeframe: str,
    since_ms: Optional[int],
    limit: int = 1000,
) -> List[Tuple[int, float, float, float, float, float]]:
    """
    Récupère OHLCV par pages (limit 1000) depuis since_ms jusqu'à ~now.
    Retourne une liste triée/dédupliquée.
    """
    out: List[Tuple[int, float, float, float, float, float]] = []
    tf_ms = parse_timeframe_to_seconds(timeframe) * 1000
    now_ms = exchange.milliseconds() if hasattr(exchange, "milliseconds") else int(time.time() * 1000)

    cursor = since_ms or (now_ms - 200 * tf_ms)
    while True:
        batch = await exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=cursor, limit=limit)
        if not batch:
            break
        for ts, o, h, l, c, v in batch:
            out.append((int(ts), float(o), float(h), float(l), float(c), float(v)))
        next_cursor = batch[-1][0] + tf_ms
        if next_cursor <= cursor:
            break
        cursor = next_cursor
        if cursor >= now_ms + (2 * tf_ms):
            break
        await asyncio.sleep(getattr(exchange, "rateLimit", 200) / 1000)

    out.sort(key=lambda x: x[0])
    dedup: List[Tuple[int, float, float, float, float, float]] = []
    seen = set()
    for row in out:
        if row[0] in seen:
            continue
        seen.add(row[0])
        dedup.append(row)
    return dedup


# ---------------------------------------------------------------------
# Cache manager
# ---------------------------------------------------------------------
async def ensure_symbol_csv_cache(
    exchange,
    symbol: str,
    timeframe: str,
    min_rows: int = CSV_MIN_ROWS,
) -> str:
    """
    Garantit qu'un CSV OHLCV récent existe pour (symbol, timeframe).
    Crée/append si nécessaire. Retourne le chemin.
    """
    path = csv_path(symbol, timeframe)
    rows = read_csv_ohlcv(path)
    tf_sec = parse_timeframe_to_seconds(timeframe)
    tf_ms = tf_sec * 1000
    now_ms = int(time.time() * 1000)

    # âge max
    max_age = CSV_MAX_AGE if CSV_MAX_AGE > 0 else int(tf_sec * STALE_FACTOR)

    need_full = False
    need_append = False

    if not rows:
        need_full = True
    else:
        last = last_ts(rows) or 0
        age_sec = max(0, (now_ms - last) // 1000)
        if age_sec > max_age or len(rows) < min_rows:
            need_append = True

    if need_full:
        since = now_ms - (tf_ms * 2000)  # ~2000 bougies
        fresh = await ccxt_fetch_ohlcv_all(exchange, symbol, timeframe, since_ms=since)
        if len(fresh) < min_rows:
            since = now_ms - (tf_ms * 5000)
            fresh = await ccxt_fetch_ohlcv_all(exchange, symbol, timeframe, since_ms=since)
        if os.path.exists(path):
            os.remove(path)
        write_csv_ohlcv(path, fresh)
        return path

    if need_append:
        since = (last_ts(rows) or now_ms - (tf_ms * 2000)) + tf_ms
        fresh = await ccxt_fetch_ohlcv_all(exchange, symbol, timeframe, since_ms=since)
        if fresh:
            write_csv_ohlcv(path, fresh)

    return path


async def prewarm_csv_cache(exchange, symbols: Iterable[str], timeframe: str) -> Dict[str, str]:
    """
    Prépare le cache pour plusieurs symboles (concurrence limitée).
    Retourne {symbol: path}.
    """
    sem = asyncio.Semaphore(PREFETCH_CONC)
    result: Dict[str, str] = {}

    async def _one(sym: str):
        async with sem:
            p = await ensure_symbol_csv_cache(exchange, sym, timeframe)
            result[sym] = p

    await asyncio.gather(*[_one(s) for s in symbols])
    return result