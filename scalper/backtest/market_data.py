# scalper/backtest/market_data.py
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable, Optional, List
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import pandas as pd

BT_DEBUG = int(os.getenv("BT_DEBUG", "0") or "0")
def _log(msg: str) -> None:
    if BT_DEBUG:
        print(f"[bt.debug] {msg}", flush=True)

# ---------- CSV ----------
def _csv_path(data_dir: str | Path, symbol: str, timeframe: str) -> Path:
    root = Path(data_dir); root.mkdir(parents=True, exist_ok=True)
    return root / f"{symbol}-{timeframe.replace(':','')}.csv"

def _read_csv(path: Path) -> pd.DataFrame:
    _log(f"lecture CSV: {path}")
    df = pd.read_csv(path)
    ts_col = next((c for c in df.columns if c.lower() in ("ts","timestamp","time","date")), None)
    if ts_col is None: raise ValueError("Colonne temps introuvable")
    df = df.rename(columns={ts_col:"timestamp"})
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, infer_datetime_format=True)
    df = df.set_index("timestamp").sort_index()
    _log(f"→ CSV ok, n={len(df)}, t0={df.index.min()}, t1={df.index.max()}")
    return df

def _write_csv(path: Path, df: pd.DataFrame) -> None:
    tmp = df.reset_index().rename(columns={"index":"timestamp"})
    if "timestamp" not in tmp.columns:
        tmp = tmp.rename(columns={"index":"timestamp"})
    tmp.to_csv(path, index=False)
    _log(f"écrit CSV: {path} (n={len(df)})")

# ---------- Normalize ----------
def _rows_to_df(rows: Iterable[Iterable[float]]) -> pd.DataFrame:
    rows = list(rows)
    if not rows: raise ValueError("OHLCV vide")
    unit = "ms" if rows[0][0] > 10_000_000_000 else "s"
    df = pd.DataFrame(rows, columns=["ts","open","high","low","close","volume"])
    df["timestamp"] = pd.to_datetime(df["ts"], unit=unit, utc=True)
    df = df.drop(columns=["ts"]).set_index("timestamp").sort_index()
    _log(f"→ OHLCV normalisé: n={len(df)}, t0={df.index.min()}, t1={df.index.max()}")
    return df

# ---------- Exchange direct ----------
def fetch_ohlcv_via_exchange(exchange: Any, symbol: str, timeframe: str, *, limit: int = 1000) -> pd.DataFrame:
    if not hasattr(exchange, "fetch_ohlcv"):
        raise AttributeError("exchange.fetch_ohlcv introuvable")
    _log(f"fetch via exchange.fetch_ohlcv: symbol={symbol} tf={timeframe} limit={limit}")
    rows = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    return _rows_to_df(rows)

# ---------- Bitget v1 HTTP (stable) ----------
_GRAN_MIX = {"1m":"1min","3m":"3min","5m":"5min","15m":"15min","30m":"30min","1h":"1h","4h":"4h","1d":"1day"}
_PERIOD_SPOT = {"1m":"1min","3m":"3min","5m":"5min","15m":"15min","30m":"30min","1h":"1hour","4h":"4hour","1d":"1day"}

def _http_get(url: str, timeout: int = 20) -> dict | list:
    req = Request(url, headers={"User-Agent":"scalper-backtest/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def _normalize_http_rows(data: dict | list) -> list[list[float]]:
    rows = data.get("data") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError(f"Réponse inattendue: {data}")
    out = []
    for r in rows:
        ts = int(str(r[0])); o,h,l,c,v = map(float, (r[1],r[2],r[3],r[4],r[5]))
        out.append([ts,o,h,l,c,v])
    out.sort(key=lambda x:x[0])
    return out

def fetch_ohlcv_via_http_bitget(symbol: str, timeframe: str, *, limit: int = 1000,
                                market_hint: Optional[str] = None, timeout: int = 20) -> pd.DataFrame:
    tf = timeframe.lower().strip()
    mix_g = _GRAN_MIX.get(tf); spot_p = _PERIOD_SPOT.get(tf)
    if not (mix_g and spot_p): raise ValueError(f"TF non supporté: {timeframe}")

    # Ordre d'essai : mix (UMCBL) puis spot (SPBL) — paramètres MINIMAUX
    trials: List[str] = []
    # mix
    trials.append(f"https://api.bitget.com/api/mix/v1/market/candles?symbol={symbol}_UMCBL&granularity={mix_g}&limit={int(limit)}")
    trials.append(f"https://api.bitget.com/api/mix/v1/market/candles?symbol={symbol}&granularity={mix_g}&limit={int(limit)}")
    # spot
    trials.append(f"https://api.bitget.com/api/spot/v1/market/candles?symbol={symbol}_SPBL&period={spot_p}&limit={int(limit)}")
    trials.append(f"https://api.bitget.com/api/spot/v1/market/candles?symbol={symbol}&period={spot_p}&limit={int(limit)}")

    last_err: Exception | None = None
    for url in trials:
        try:
            _log(f"HTTP v1: GET {url}")
            data = _http_get(url, timeout=timeout)
            # format {code,msg,data} possible
            if isinstance(data, dict) and "code" in data and str(data["code"]) != "00000" and "data" not in data:
                raise RuntimeError(f"Bitget error {data.get('code')}: {data.get('msg')}")
            rows = _normalize_http_rows(data)
            if not rows:
                raise ValueError("Réponse vide")
            _log(f"HTTP OK v1 ({len(rows)} bougies)")
            return _rows_to_df(rows)
        except (URLError, HTTPError, ValueError, KeyError, RuntimeError) as e:
            last_err = e
            _log(f"HTTP fail v1: {e}")
            continue
    raise last_err or RuntimeError(f"Bitget OHLCV HTTP KO pour {symbol} {timeframe}")

# ---------- Loader hybride ----------
def hybrid_loader(data_dir: str = "data", *, exchange: Any | None = None,
                  market_hint: Optional[str] = None, api_limit: int = 1000):
    """
    1) lit data/<SYMBOL>-<TF>.csv si présent,
    2) sinon via exchange.fetch_ohlcv (si fourni),
    3) sinon via HTTP Bitget v1 (stable),
    puis écrit le CSV en cache.
    """
    def load(symbol: str, timeframe: str, start: str | None, end: str | None) -> pd.DataFrame:
        path = _csv_path(data_dir, symbol, timeframe)
        src = "csv"
        if path.exists():
            df = _read_csv(path)
        else:
            if exchange is not None and hasattr(exchange, "fetch_ohlcv"):
                try:
                    df = fetch_ohlcv_via_exchange(exchange, symbol, timeframe, limit=api_limit)
                    src = "exchange"
                except Exception as e:
                    _log(f"fallback HTTP v1 (exchange KO): {e}")
                    df = fetch_ohlcv_via_http_bitget(symbol, timeframe, limit=api_limit, market_hint=market_hint)
                    src = "http"
            else:
                df = fetch_ohlcv_via_http_bitget(symbol, timeframe, limit=api_limit, market_hint=market_hint)
                src = "http"
            _write_csv(path, df)

        if start: df = df.loc[pd.Timestamp(start, tz="UTC") :]
        if end:   df = df.loc[: pd.Timestamp(end, tz="UTC")]
        _log(f"loader -> {symbol} {timeframe} (src={src}) n={len(df)} "
             f"range=[{df.index.min()} .. {df.index.max()}]")
        return df
    return load

def hybrid_loader_from_exchange(exchange: Any, data_dir: str = "data", *, api_limit: int = 1000):
    return hybrid_loader(data_dir=data_dir, exchange=exchange, market_hint=None, api_limit=api_limit)