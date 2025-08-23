# scalper/backtest/cache.py
from __future__ import annotations

import csv
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Iterable, Optional

# ---------------- Timeframe utils ----------------

_TF_SECONDS = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600, "12h": 43200,
    "1d": 86400, "3d": 259200, "1w": 604800,
}

def tf_to_seconds(tf: str) -> int:
    tf = tf.strip().lower()
    if tf not in _TF_SECONDS:
        raise ValueError(f"Timeframe inconnu: {tf}")
    return _TF_SECONDS[tf]

# ---------------- Fraîcheur cible par TF ----------------

_DEFAULT_MAX_AGE = {
    # règle empirique (peut être surchargée par ENV)
    "1m": 2 * 3600,        # 2h
    "3m": 4 * 3600,        # 4h
    "5m": 12 * 3600,       # 12h
    "15m": 24 * 3600,      # 24h
    "30m": 36 * 3600,      # 36h
    "1h": 3 * 86400,       # 3 jours
    "2h": 5 * 86400,       # 5 jours
    "4h": 10 * 86400,      # 10 jours
    "6h": 15 * 86400,      # 15 jours
    "12h": 20 * 86400,     # 20 jours
    "1d": 3 * 86400,       # 3 jours (ok si 2 jours comme tu voulais)
    "3d": 10 * 86400,
    "1w": 30 * 86400,
}

def max_age_for_tf(tf: str) -> int:
    """Autorise override ENV via BACKTEST_MAX_AGE_<TF> (en secondes)."""
    tf = tf.lower()
    env_key = f"BACKTEST_MAX_AGE_{tf.replace('m','M').replace('h','H').replace('d','D').replace('w','W')}"
    if env_key in os.environ:
        try:
            return int(os.environ[env_key])
        except Exception:
            pass
    return _DEFAULT_MAX_AGE.get(tf, 7 * 86400)

# ---------------- CSV I/O ----------------

def data_dir() -> Path:
    d = Path(os.getenv("DATA_DIR", "data"))
    d.mkdir(parents=True, exist_ok=True)
    return d

def csv_path(symbol: str, tf: str) -> Path:
    return data_dir() / f"{symbol.upper()}-{tf}.csv"

def read_csv_ohlcv(path: Path) -> List[List[float]]:
    out: List[List[float]] = []
    if not path.exists():
        return out
    with path.open("r", newline="") as f:
        r = csv.reader(f)
        header = next(r, None)
        for row in r:
            # columns: timestamp,open,high,low,close,volume
            try:
                ts, o, h, l, c, v = row[:6]
                out.append([int(ts), float(o), float(h), float(l), float(c), float(v)])
            except Exception:
                continue
    return out

def write_csv_ohlcv(path: Path, rows: Iterable[Iterable[float]]) -> None:
    new_file = not path.exists()
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp","open","high","low","close","volume"])
        for r in rows:
            w.writerow(r)

# ---------------- Validation / Chargement / Fetch ----------------

@dataclass
class CacheInfo:
    symbol: str
    tf: str
    path: Path
    exists: bool
    fresh: bool
    last_ts: Optional[int] = None
    rows: int = 0

def _is_fresh(last_ts: Optional[int], tf: str) -> bool:
    if not last_ts:
        return False
    age = int(time.time()) - int(last_ts / 1000)
    return age <= max_age_for_tf(tf)

def inspect_csv(symbol: str, tf: str) -> CacheInfo:
    p = csv_path(symbol, tf)
    if not p.exists():
        return CacheInfo(symbol, tf, p, exists=False, fresh=False)
    rows = read_csv_ohlcv(p)
    last_ts = rows[-1][0] if rows else None
    return CacheInfo(symbol, tf, p, exists=True, fresh=_is_fresh(last_ts, tf), last_ts=last_ts, rows=len(rows))

async def fetch_ohlcv_via_exchange(exchange, symbol: str, tf: str, limit: int) -> List[List[float]]:
    # exchange: objet CCXT-like fourni par le live (déjà configuré Bitget)
    return await exchange.fetch_ohlcv(symbol=symbol, timeframe=tf, limit=limit)

async def ensure_csv_for_symbol(exchange, symbol: str, tf: str, limit: int) -> Tuple[CacheInfo, List[List[float]]]:
    info = inspect_csv(symbol, tf)
    if info.exists and info.fresh:
        data = read_csv_ohlcv(info.path)
        return info, data

    # fetch & persist
    data = await fetch_ohlcv_via_exchange(exchange, symbol, tf, limit=limit)
    if data:
        write_csv_ohlcv(info.path, data)
        info = inspect_csv(symbol, tf)  # refresh stats
    return info, data

async def ensure_csv_cache(exchange, symbols: List[str], tf: str, limit: int) -> Dict[str, List[List[float]]]:
    """Vérifie le cache CSV et (re)charge depuis l'exchange si nécessaire."""
    out: Dict[str, List[List[float]]] = {}
    for s in symbols:
        info, rows = await ensure_csv_for_symbol(exchange, s, tf, limit)
        out[s] = rows
    return out

def dump_validation_report(symbols: List[str], tf: str, out_path: Path) -> None:
    report = []
    for s in symbols:
        info = inspect_csv(s, tf)
        report.append({
            "symbol": s,
            "tf": tf,
            "path": str(info.path),
            "exists": info.exists,
            "fresh": info.fresh,
            "last_ts": info.last_ts,
            "rows": info.rows,
            "max_age": max_age_for_tf(tf),
        })
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2))