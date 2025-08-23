# scalper/backtest/market_data.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
import asyncio
import inspect


# --------- utilitaires CSV ---------

def _csv_path(data_dir: str | Path, symbol: str, timeframe: str) -> Path:
    root = Path(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    tf = timeframe.replace(":", "")
    return root / f"{symbol}-{tf}.csv"

def _read_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    ts_col = next((c for c in df.columns if c.lower() in ("ts", "timestamp", "time", "date")), None)
    if ts_col is None:
        raise ValueError("Colonne temps introuvable (timestamp/time/date)")
    df = df.rename(columns={ts_col: "timestamp"})
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, infer_datetime_format=True)
    return df.set_index("timestamp").sort_index()

def _write_csv(path: Path, df: pd.DataFrame) -> None:
    tmp = df.reset_index().rename(columns={"index": "timestamp"})
    if "timestamp" not in tmp.columns:
        tmp = tmp.rename(columns={"index": "timestamp"})
    tmp.to_csv(path, index=False)


# --------- loader via exchange (public, sync/async) ---------

def _sync_call_fetch_ohlcv(exchange, symbol: str, timeframe: str, *, limit: int):
    """
    Appelle exchange.fetch_ohlcv en supportant :
      - fonction synchrone -> liste
      - coroutine (async)   -> attendue via une event-loop locale (thread executor)
    """
    fn = getattr(exchange, "fetch_ohlcv")
    res = fn(symbol, timeframe=timeframe, limit=limit)

    # Si la fonction a été appelée et renvoie un awaitable -> l'attendre
    if inspect.isawaitable(res):
        # Dans l'executor, pas d'event-loop active -> on peut utiliser asyncio.run
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(fn(symbol, timeframe=timeframe, limit=limit))
        else:
            # Cas plus rare: déjà dans une loop -> exécuter thread-safe
            fut = asyncio.run_coroutine_threadsafe(
                fn(symbol, timeframe=timeframe, limit=limit), loop
            )
            return fut.result()

    return res


def fetch_ohlcv_via_exchange(
    exchange,
    symbol: str,
    timeframe: str,
    *,
    limit: int = 1000,
) -> pd.DataFrame:
    """
    Utilise exchange.fetch_ohlcv(symbol, timeframe, limit) tel que déjà utilisé en live.
    Retourne un DataFrame indexé en UTC avec colonnes: open, high, low, close, volume.
    """
    raw = _sync_call_fetch_ohlcv(exchange, symbol, timeframe, limit=limit)
    if not raw:
        raise ValueError(f"fetch_ohlcv a renvoyé vide pour {symbol} {timeframe}")

    # raw: [[ts, o, h, l, c, v], ...] (ms ou s)
    rows = []
    for r in raw:
        ts = int(r[0])
        unit = "ms" if ts > 10_000_000_000 else "s"
        rows.append(
            {
                "timestamp": pd.to_datetime(ts, unit=unit, utc=True),
                "open": float(r[1]),
                "high": float(r[2]),
                "low": float(r[3]),
                "close": float(r[4]),
                "volume": float(r[5]),
            }
        )
    df = pd.DataFrame(rows).set_index("timestamp").sortindex() if hasattr(pd.DataFrame, "sortindex") else pd.DataFrame(rows).set_index("timestamp").sort_index()
    return df


def hybrid_loader_from_exchange(
    exchange,
    data_dir: str = "data",
    *,
    api_limit: int = 1000,
):
    """
    Loader hybride:
      1) tente de lire data/<SYMBOL>-<TF>.csv
      2) sinon demande à l'exchange (fetch_ohlcv), puis écrit le CSV en cache.
    """
    def load(symbol: str, timeframe: str, start: str | None, end: str | None) -> pd.DataFrame:
        path = _csv_path(data_dir, symbol, timeframe)
        if path.exists():
            df = _read_csv(path)
        else:
            df = fetch_ohlcv_via_exchange(exchange, symbol, timeframe, limit=api_limit)
            _write_csv(path, df)

        if start:
            df = df.loc[pd.Timestamp(start, tz="UTC") :]
        if end:
            df = df.loc[: pd.Timestamp(end, tz="UTC")]
        return df

    return load