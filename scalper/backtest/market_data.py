# scalper/backtest/market_data.py
from __future__ import annotations

from pathlib import Path
from typing import Optional, Any, Iterable

import pandas as pd
import asyncio
import inspect


# ---------------- utilitaires CSV ----------------

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


# ---------------- appel résilient à fetch_ohlcv ----------------

def _await_if_needed(val: Any) -> Any:
    """Attend la valeur si c'est un awaitable (utilisé dans un thread)."""
    if inspect.isawaitable(val):
        # Dans le thread d'executor, on n'a pas d'event loop -> OK pour asyncio.run
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(val)
        else:
            # cas rare: déjà dans une loop (pas normalement dans l'executor)
            fut = asyncio.run_coroutine_threadsafe(val, asyncio.get_running_loop())
            return fut.result()
    return val

def _try_call_variants(fn, symbol: str, timeframe: str, limit: int) -> Any:
    """
    Essaie plusieurs signatures courantes (CCXT & wrappers):
      1) fn(symbol, timeframe=timeframe, limit=limit)
      2) fn(symbol, timeframe)
      3) fn(symbol, timeframe=timeframe, since=None, limit=limit)
      4) fn(symbol, timeframe, None, limit)
      5) fn(symbol, timeframe=timeframe)   # certaines implémentations ignorent limit
    Retourne le résultat (peut être awaitable).
    """
    variants = (
        ((), dict(symbol=symbol, timeframe=timeframe, limit=limit)),    # kw
        ((symbol, timeframe), {}),                                      # pos
        ((), dict(symbol=symbol, timeframe=timeframe, since=None, limit=limit)),  # kw ccxt typique
        ((symbol, timeframe, None, limit), {}),                         # pos ccxt
        ((), dict(symbol=symbol, timeframe=timeframe)),                 # sans limit
    )

    last_err: Optional[Exception] = None
    for args, kwargs in variants:
        try:
            if args:
                res = fn(*args)
            else:
                res = fn(**kwargs)
            return _await_if_needed(res)
        except TypeError as e:
            # signature incompatible -> on tente la suivante
            last_err = e
            continue
    # si on arrive ici, on remonte la dernière erreur de signature
    raise last_err or RuntimeError("fetch_ohlcv: aucune signature compatible")

def _normalize_ohlcv(raw: Any) -> list[list[float]]:
    """
    Accepte plusieurs formats de retour et convertit en [[ts,o,h,l,c,v], ...].
    """
    if raw is None:
        raise ValueError("fetch_ohlcv a renvoyé None")

    # dict {data:[...]} -> prend data
    if isinstance(raw, dict) and "data" in raw:
        raw = raw["data"]

    # pandas DataFrame -> colonnes (ou, hlcv) avec index temps
    if isinstance(raw, pd.DataFrame):
        if "open" in raw.columns and "close" in raw.columns:
            df = raw.copy()
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, infer_datetime_format=True)
                df = df.set_index("timestamp").sort_index()
            if df.index.name and "time" in df.index.name.lower():
                pass
            df = df[["open", "high", "low", "close", "volume"]]
            return [[int(ts.value // 10**6), *map(float, row)] for ts, row in df.itertuples()]
        raise ValueError("DataFrame OHLCV inattendu: colonnes manquantes")

    # liste de listes (format ccxt)
    if isinstance(raw, (list, tuple)) and raw and isinstance(raw[0], (list, tuple)):
        out = []
        for r in raw:
            ts = int(r[0])
            o, h, l, c, v = map(float, (r[1], r[2], r[3], r[4], r[5]))
            out.append([ts, o, h, l, c, v])
        return out

    raise ValueError(f"Format OHLCV inattendu: {type(raw)}")


def fetch_ohlcv_via_exchange(
    exchange,
    symbol: str,
    timeframe: str,
    *,
    limit: int = 1000,
) -> pd.DataFrame:
    """
    Utilise exchange.fetch_ohlcv en supportant sync/async et signatures variées.
    Retour: DataFrame index UTC, colonnes: open, high, low, close, volume.
    """
    fn = getattr(exchange, "fetch_ohlcv", None)
    if fn is None:
        raise AttributeError("exchange.fetch_ohlcv introuvable")

    raw = _try_call_variants(fn, symbol, timeframe, limit)
    rows = _normalize_ohlcv(raw)

    # ts en s ou ms -> heuristique
    unit = "ms" if rows and rows[0][0] > 10_000_000_000 else "s"
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["ts"], unit=unit, utc=True)
    return df.drop(columns=["ts"]).set_index("timestamp").sort_index()


def hybrid_loader_from_exchange(
    exchange,
    data_dir: str = "data",
    *,
    api_limit: int = 1000,
):
    """
    Loader hybride:
      1) lit data/<SYMBOL>-<TF>.csv si présent,
      2) sinon fetch via exchange.fetch_ohlcv, puis écrit le CSV en cache.
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