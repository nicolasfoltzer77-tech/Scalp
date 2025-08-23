# scalper/backtest/market_data.py
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import pandas as pd

# ---------------------------------------------------------------------------
# Debug
# ---------------------------------------------------------------------------
BT_DEBUG = int(os.getenv("BT_DEBUG", "0") or "0")

def _log(msg: str) -> None:
    if BT_DEBUG:
        print(f"[bt.debug] {msg}", flush=True)

# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Normalisation OHLCV → DataFrame
# ---------------------------------------------------------------------------
def _rows_to_df(rows: Iterable[Iterable[float]]) -> pd.DataFrame:
    rows = list(rows)
    if not rows:
        raise ValueError("OHLCV vide")
    unit = "ms" if rows[0][0] > 10_000_000_000 else "s"
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["ts"], unit=unit, utc=True)
    df = df.drop(columns=["ts"]).set_index("timestamp").sort_index()
    _log(f"→ OHLCV normalisé: n={len(df)}, t0={df.index.min()}, t1={df.index.max()}")
    return df

# ---------------------------------------------------------------------------
# 1) Source: exchange.fetch_ohlcv si dispo (sync/async via simple appel direct)
# ---------------------------------------------------------------------------
def fetch_ohlcv_via_exchange(exchange: Any, symbol: str, timeframe: str, *, limit: int = 1000) -> pd.DataFrame:
    if not hasattr(exchange, "fetch_ohlcv"):
        raise AttributeError("exchange.fetch_ohlcv introuvable")
    _log(f"fetch via exchange.fetch_ohlcv: symbol={symbol} tf={timeframe} limit={limit}")
    rows = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    # attendu: [[ts,o,h,l,c,v], ...]
    return _rows_to_df(rows)

# ---------------------------------------------------------------------------
# 2) Source: HTTP Bitget public (sans CCXT)
# ---------------------------------------------------------------------------
_GRAN_MIX = {  # mix: granularity
    "1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min",
    "30m": "30min", "1h": "1h", "4h": "4h", "1d": "1day",
}
_PERIOD_SPOT = {  # spot: period
    "1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min",
    "30m": "30min", "1h": "1hour", "4h": "4hour", "1d": "1day",
}

def _http_get(url: str, timeout: int = 20) -> dict | list:
    req = Request(url, headers={"User-Agent": "scalper-backtest/1.3"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def _sym_variants(sym: str) -> list[str]:
    s = sym.upper()
    out = [s]
    if not s.endswith("_UMCBL"):
        out.append(f"{s}_UMCBL")
    if not s.endswith("_SPBL"):
        out.append(f"{s}_SPBL")
    return out

def _normalize_http_rows(data: dict | list) -> list[list[float]]:
    rows = data.get("data") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError(f"Réponse OHLCV inattendue: {data}")
    out = []
    for r in rows:
        # attendu: [ts, open, high, low, close, volume, ...] (ts en ms)
        ts = int(str(r[0]))
        o, h, l, c, v = map(float, (r[1], r[2], r[3], r[4], r[5]))
        out.append([ts, o, h, l, c, v])
    return out

def fetch_ohlcv_via_http_bitget(
    symbol: str,
    timeframe: str,
    *,
    limit: int = 1000,
    market_hint: Optional[str] = None,  # "mix" | "spot" | None
    timeout: int = 20,
    max_retries: int = 3,
) -> pd.DataFrame:
    """
    Essaie en cascade:
      - mix candles (granularity=5min) sur <SYM> et <SYM>_UMCBL
      - spot candles (period=5min) sur <SYM> et <SYM>_SPBL
    Utilise les endpoints publics v1.
    """
    tf = timeframe.lower().strip()
    mix_g = _GRAN_MIX.get(tf)
    spot_p = _PERIOD_SPOT.get(tf)
    if not mix_g or not spot_p:
        raise ValueError(f"Timeframe non supporté: {timeframe}")

    base_mix = "https://api.bitget.com/api/mix/v1/market/candles"
    base_spot = "https://api.bitget.com/api/spot/v1/market/candles"

    # ordre d'essais selon hint
    paths = []
    if (market_hint or "").lower() == "mix":
        paths += [("mix", base_mix, "granularity", mix_g)]
        paths += [("spot", base_spot, "period", spot_p)]
    elif (market_hint or "").lower() == "spot":
        paths += [("spot", base_spot, "period", spot_p)]
        paths += [("mix", base_mix, "granularity", mix_g)]
    else:
        paths += [("mix", base_mix, "granularity", mix_g), ("spot", base_spot, "period", spot_p)]

    last_err: Optional[Exception] = None
    for market, base, tf_key, tf_val in paths:
        for sym in _sym_variants(symbol):
            url = f"{base}?symbol={sym}&{tf_key}={tf_val}&limit={int(limit)}"
            for attempt in range(max_retries + 1):
                try:
                    _log(f"HTTP Bitget {market}: GET {url}")
                    data = _http_get(url, timeout=timeout)
                    # certains endpoints renvoient {code,msg,data}
                    if isinstance(data, dict) and "code" in data and str(data["code"]) != "00000" and "data" not in data:
                        raise RuntimeError(f"Bitget error {data.get('code')}: {data.get('msg')}")
                    rows = _normalize_http_rows(data)
                    _log(f"HTTP OK via {market} {sym} ({len(rows)} bougies)")
                    return _rows_to_df(rows)
                except (URLError, HTTPError, ValueError, KeyError, RuntimeError) as e:
                    last_err = e
                    time.sleep(min(2 ** attempt, 5))
                    continue
    raise last_err or RuntimeError(f"Bitget OHLCV HTTP KO pour {symbol} {timeframe}")

# ---------------------------------------------------------------------------
# Loader hybride : CSV → exchange → HTTP Bitget, avec cache CSV
# ---------------------------------------------------------------------------
def hybrid_loader(
    data_dir: str = "data",
    *,
    exchange: Any | None = None,
    market_hint: Optional[str] = None,  # "spot" | "mix" | None
    api_limit: int = 1000,
):
    """
    1) lit data/<SYMBOL>-<TF>.csv si présent,
    2) sinon via exchange.fetch_ohlcv (si fourni),
    3) sinon via HTTP Bitget public,
    puis écrit le CSV en cache.
    """
    def load(symbol: str, timeframe: str, start: str | None, end: str | None) -> pd.DataFrame:
        path = _csv_path(data_dir, symbol, timeframe)
        src = "csv"
        if path.exists():
            df = _read_csv(path)
        else:
            # via exchange
            if exchange is not None and hasattr(exchange, "fetch_ohlcv"):
                try:
                    df = fetch_ohlcv_via_exchange(exchange, symbol, timeframe, limit=api_limit)
                    src = "exchange"
                except Exception as e:
                    _log(f"fallback HTTP (exchange KO): {e}")
                    df = fetch_ohlcv_via_http_bitget(symbol, timeframe, limit=api_limit, market_hint=market_hint)
                    src = "http"
            else:
                df = fetch_ohlcv_via_http_bitget(symbol, timeframe, limit=api_limit, market_hint=market_hint)
                src = "http"
            _write_csv(path, df)

        if start:
            df = df.loc[pd.Timestamp(start, tz="UTC") :]
        if end:
            df = df.loc[: pd.Timestamp(end, tz="UTC")]
        _log(f"loader -> {symbol} {timeframe} (src={src}) n={len(df)} "
             f"range=[{df.index.min()} .. {df.index.max()}]")
        return df

    return load

# compat (appelée par backtest_telegram)
def hybrid_loader_from_exchange(
    exchange: Any,
    data_dir: str = "data",
    *,
    api_limit: int = 1000,
):
    return hybrid_loader(
        data_dir=data_dir,
        exchange=exchange,
        market_hint=None,
        api_limit=api_limit,
    )