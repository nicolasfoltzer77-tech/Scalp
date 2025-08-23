# scalper/services/data_cache.py
from __future__ import annotations

import asyncio
import csv
import os
import time
from typing import Iterable, List, Optional, Tuple, Dict, Any

# -----------------------------------------------------------------------------
# Réglages via env
# -----------------------------------------------------------------------------
DATA_DIR = os.getenv("DATA_DIR", "/notebooks/data")           # dossier PERSISTANT (hors-git)
CSV_MAX_AGE = int(os.getenv("CSV_MAX_AGE_SECONDS", "0"))      # 0 = auto par timeframe
CSV_MIN_ROWS = int(os.getenv("CSV_MIN_ROWS", "200"))          # fail si trop peu de lignes
STALE_FACTOR = float(os.getenv("CSV_STALE_FACTOR", "6"))      # âge max = STALE_FACTOR * tf_sec

os.makedirs(DATA_DIR, exist_ok=True)


# -----------------------------------------------------------------------------
# Utils
# -----------------------------------------------------------------------------
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
    fname = f"{symbol}-{timeframe}.csv"
    return os.path.join(DATA_DIR, fname)


def read_csv_ohlcv(path: str) -> List[Tuple[int, float, float, float, float, float]]:
    rows: List[Tuple[int, float, float, float, float, float]] = []
    if not os.path.exists(path):
        return rows
    with open(path, "r", newline="") as f:
        r = csv.reader(f)
        header = next(r, None)
        # Accepte soit header standard soit brut
        # attendu: timestamp,open,high,low,close,volume
        for line in r:
            if not line:
                continue
            ts, o, h, l, c, v = line[:6]
            rows.append((int(ts), float(o), float(h), float(l), float(c), float(v)))
    return rows


def write_csv_ohlcv(path: str, data: Iterable[Tuple[int, float, float, float, float, float]]) -> None:
    first_write = not os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if first_write:
            w.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for row in data:
            w.writerow(row)


def last_ts(rows: List[Tuple[int, float, float, float, float, float]]) -> Optional[int]:
    return rows[-1][0] if rows else None


# -----------------------------------------------------------------------------
# CCXT fetch
# -----------------------------------------------------------------------------
async def ccxt_fetch_ohlcv_all(
    exchange, symbol: str, timeframe: str, since_ms: Optional[int], limit: int = 1000
) -> List[Tuple[int, float, float, float, float, float]]:
    """
    Récupère OHLCV par pages (limit 1000) depuis 'since_ms' jusqu'à maintenant.
    Retourne une liste triée par ts croissant.
    """
    out: List[Tuple[int, float, float, float, float, float]] = []
    tf_ms = parse_timeframe_to_seconds(timeframe) * 1000
    now = exchange.milliseconds()

    cursor = since_ms or (now - 200 * tf_ms)  # par sécurité si since None
    while True:
        batch = await exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=cursor, limit=limit)
        if not batch:
            break
        # normalise en tuples
        for ts, o, h, l, c, v in batch:
            out.append((int(ts), float(o), float(h), float(l), float(c), float(v)))
        # avance le curseur (évite boucle infinie si même ts)
        next_cursor = batch[-1][0] + tf_ms
        if next_cursor <= cursor:
            break
        cursor = next_cursor
        # stop si on est arrivé au présent (2 * tf d'avance)
        if cursor >= now + (2 * tf_ms):
            break
        # évite spam API
        await asyncio.sleep(exchange.rateLimit / 1000 if getattr(exchange, "rateLimit", None) else 0.2)

    # dé-duplique et ordonne
    out.sort(key=lambda x: x[0])
    dedup: List[Tuple[int, float, float, float, float, float]] = []
    seen = set()
    for row in out:
        if row[0] in seen:
            continue
        seen.add(row[0])
        dedup.append(row)
    return dedup


# -----------------------------------------------------------------------------
# Cache manager
# -----------------------------------------------------------------------------
async def ensure_symbol_csv_cache(
    exchange, symbol: str, timeframe: str, min_rows: int = CSV_MIN_ROWS
) -> str:
    """
    Garantit qu'un CSV OHLCV récent existe en DATA_DIR pour (symbol, timeframe).
    - crée ou met à jour si trop vieux
    - retourne le chemin vers le CSV
    """
    path = csv_path(symbol, timeframe)
    rows = read_csv_ohlcv(path)
    tf_sec = parse_timeframe_to_seconds(timeframe)
    tf_ms = tf_sec * 1000
    now_ms = int(time.time() * 1000)

    # âge max autorisé
    max_age = CSV_MAX_AGE if CSV_MAX_AGE > 0 else int(tf_sec * STALE_FACTOR)

    need_full = False
    need_append = False

    if not rows:
        need_full = True
    else:
        last = last_ts(rows) or 0
        age_sec = max(0, (now_ms - last) // 1000)
        if age_sec > max_age:
            need_append = True
        if len(rows) < min_rows:
            # Trop court → on repart plus loin pour étoffer
            need_append = True

    if need_full:
        since = now_ms - (1000 * tf_sec * 2000)  # ~2000 bougies par défaut
        fresh = await ccxt_fetch_ohlcv_all(exchange, symbol, timeframe, since_ms=since)
        if len(fresh) < min_rows:
            # on essaye plus loin
            since = now_ms - (1000 * tf_sec * 5000)
            fresh = await ccxt_fetch_ohlcv_all(exchange, symbol, timeframe, since_ms=since)
        # (ré)écrit
        if os.path.exists(path):
            os.remove(path)
        write_csv_ohlcv(path, fresh)
        return path

    if need_append:
        last = last_ts(rows) or (now_ms - (1000 * tf_sec * 2000))
        since = last + tf_ms
        fresh = await ccxt_fetch_ohlcv_all(exchange, symbol, timeframe, since_ms=since)
        # append uniquement les nouvelles lignes
        if fresh:
            write_csv_ohlcv(path, fresh)

    return path


async def prewarm_csv_cache(exchange, symbols: Iterable[str], timeframe: str) -> Dict[str, str]:
    """
    Prépare le cache CSV pour une liste de symboles (en parallèle limité).
    Retourne {symbol: path_csv}
    """
    sem = asyncio.Semaphore(int(os.getenv("CSV_PREFETCH_CONC", "4")))
    results: Dict[str, str] = {}

    async def _one(sym: str):
        async with sem:
            p = await ensure_symbol_csv_cache(exchange, sym, timeframe)
            results[sym] = p

    await asyncio.gather(*[_one(s) for s in symbols])
    return results