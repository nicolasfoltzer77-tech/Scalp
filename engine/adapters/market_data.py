# scalper/backtest/market_data.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd

BT_DEBUG = int(os.getenv("BT_DEBUG", "0") or "0")

def _log(msg: str) -> None:
    if BT_DEBUG:
        print(f"[bt.debug] {msg}", flush=True)

def _csv_path(data_dir: str | Path, symbol: str, timeframe: str) -> Path:
    root = Path(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    tf = timeframe.replace(":", "")
    return root / f"{symbol}-{tf}.csv"

def _read_csv(path: Path) -> pd.DataFrame:
    _log(f"lecture CSV: {path}")
    df = pd.read_csv(path)
    ts_col = next((c for c in df.columns if c.lower() in ("ts", "timestamp", "time", "date")), None)
    if ts_col is None:
        raise ValueError("Colonne temps introuvable (timestamp/time/date)")
    df = df.rename(columns={ts_col: "timestamp"})
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, infer_datetime_format=True)
    df = df.set_index("timestamp").sort_index()
    _log(f"→ CSV ok, n={len(df)}, t0={df.index.min()}, t1={df.index.max()}")
    return df

def _write_csv(path: Path, df: pd.DataFrame) -> None:
    tmp = df.reset_index().rename(columns={"index": "timestamp"})
    if "timestamp" not in tmp.columns:
        tmp = tmp.rename(columns={"index": "timestamp"})
    tmp.to_csv(path, index=False)
    _log(f"écrit CSV: {path} (n={len(df)})")

def fetch_ohlcv_via_exchange(exchange: Any, symbol: str, timeframe: str, *, limit: int = 1000) -> pd.DataFrame:
    _log(f"fetch via exchange.fetch_ohlcv: symbol={symbol} tf={timeframe} limit={limit}")
    raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)  # peut être sync ou adapté
    # Normalisation minimaliste (liste de listes)
    rows = []
    for r in raw:
        ts = int(r[0])
        unit = "ms" if ts > 10_000_000_000 else "s"
        ts = pd.to_datetime(ts, unit=unit, utc=True)
        rows.append([ts, float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])])
    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"]).set_index("timestamp").sort_index()
    _log(f"→ exchange ok, n={len(df)}, t0={df.index.min()}, t1={df.index.max()}")
    return df

def hybrid_loader_from_exchange(exchange: Any, data_dir: str = "data", *, api_limit: int = 1000):
    """
    Loader hybride:
      1) lit data/<SYMBOL>-<TF>.csv si présent,
      2) sinon fetch via exchange.fetch_ohlcv, puis écrit le CSV en cache.
    """
    def load(symbol: str, timeframe: str, start: str | None, end: str | None) -> pd.DataFrame:
        path = _csv_path(data_dir, symbol, timeframe)
        if path.exists():
            df = _read_csv(path)
            src = "csv"
        else:
            df = fetch_ohlcv_via_exchange(exchange, symbol, timeframe, limit=api_limit)
            _write_csv(path, df)
            src = "exchange"
        if start:
            df = df.loc[pd.Timestamp(start, tz="UTC") :]
        if end:
            df = df.loc[: pd.Timestamp(end, tz="UTC")]
        _log(f"loader -> {symbol} {timeframe} (src={src}) n={len(df)} "
             f"range=[{df.index.min()} .. {df.index.max()}]")
        return df
    return load