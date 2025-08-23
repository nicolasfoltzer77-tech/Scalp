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
# 1) Source: exchange.fetch_ohlcv si dispo
# ---------------------------------------------------------------------------
def fetch_ohlcv_via_exchange(exchange: Any, symbol: str, timeframe: str, *, limit: int = 1000) -> pd.DataFrame:
    if not hasattr(exchange, "fetch_ohlcv"):
        raise AttributeError("exchange.fetch_ohlcv introuvable")
    _log(f"fetch via exchange.fetch_ohlcv: symbol={symbol} tf={timeframe} limit={limit}")
    rows = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)  # attendu: [[ts,o,h,l,c,v], ...]
    return _rows_to_df(rows)

# ---------------------------------------------------------------------------
# 2) Source: HTTP Bitget public (sans CCXT) — avec start/end automatiques
# ---------------------------------------------------------------------------
_GRAN_MIX = {  # mix: granularity
    "1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min",
    "30m": "30min", "1h": "1h", "4h": "4h", "1d": "1day",
}
_PERIOD_SPOT = {  # spot: period
    "1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min",
    "30m": "30min", "1h": "1hour", "4h": "4hour", "1d": "1day",
}
_TF_SECS = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900,
    "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400,
}

def _http_get(url: str, timeout: int = 20) -> dict | list:
    req = Request(url, headers={"User-Agent": "scalper-backtest/1.4"})
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
        ts = int(str(r[0]))
        o, h, l, c, v = map(float, (r[1], r[2], r[3], r[4], r[5]))
        out.append([ts, o, h, l, c, v])
    # Bitget peut renvoyer décroissant → on trie par ts ascendant
    out.sort(key=lambda x: x[0])
    return out

def _build_urls(base: str, *, symbol: str, tf_key: str, tf_val: str, limit: int,
                start_ms: int, end_ms: int, is_spot: bool) -> list[str]:
    """
    Construit plusieurs variantes avec/ sans startTime/endTime selon l'API.
    Spot accepte parfois 'after' (point de départ) au lieu de startTime.
    """
    urls = [
        f"{base}?symbol={symbol}&{tf_key}={tf_val}&limit={limit}&startTime={start_ms}&endTime={end_ms}",
        f"{base}?symbol={symbol}&{tf_key}={tf_val}&limit={limit}&startTime={start_ms}",
        f"{base}?symbol={symbol}&{tf_key}={tf_val}&limit={limit}&start={start_ms}&end={end_ms}",
    ]
    if is_spot:
        # variantes spot (certains endpoints utilisent 'after' pour la borne)
        urls.append(f"{base}?symbol={symbol}&{tf_key}={tf_val}&limit={limit}&after={start_ms}")
        urls.append(f"{base}?symbol={symbol}&{tf_key}={tf_val}&limit={limit}&after={end_ms}")
    # version minimale (certains serveurs n'aiment aucun filtre)
    urls.append(f"{base}?symbol={symbol}&{tf_key}={tf_val}&limit={limit}")
    return urls

def fetch_ohlcv_via_http_bitget(
    symbol: str,
    timeframe: str,
    *,
    limit: int = 1000,
    market_hint: Optional[str] = None,  # "mix" | "spot" | None
    timeout: int = 20,
    max_retries: int = 2,
) -> pd.DataFrame:
    """
    Essaie en cascade:
      - mix candles (granularity=5min) sur <SYM>, <SYM>_UMCBL
      - spot candles (period=5min) sur <SYM>, <SYM>_SPBL
    En fournissant une fenêtre de temps par défaut (≈ 1.5 * limit * tf).
    """
    tf = timeframe.lower().strip()
    mix_g = _GRAN_MIX.get(tf)
    spot_p = _PERIOD_SPOT.get(tf)
    secs = _TF_SECS.get(tf)
    if not (mix_g and spot_p and secs):
        raise ValueError(f"Timeframe non supporté: {timeframe}")

    # Fenêtre temporelle par défaut ~ 1.5 * limit * tf
    now = int(time.time() * 1000)
    window = int(limit * secs * 1000 * 1.5)
    start = now - window
    end = now

    base_mix = "https://api.bitget.com/api/mix/v1/market/candles"
    base_spot = "https://api.bitget.com/api/spot/v1/market/candles"

    # ordre d'essais selon hint
    plans: list[tuple[str, str, str, str, bool]] = []
    if (market_hint or "").lower() == "mix":
        plans += [("mix", base_mix, "granularity", mix_g, False), ("spot", base_spot, "period", spot_p, True)]
    elif (market_hint or "").lower() == "spot":
        plans += [("spot", base_spot, "period", spot_p, True), ("mix", base_mix, "granularity", mix_g, False)]
    else:
        plans += [("mix", base_mix, "granularity", mix_g, False), ("spot", base_spot, "period", spot_p, True)]

    last_err: Optional[Exception] = None
    for market, base, tf_key, tf_val, is_spot in plans:
        for sym in _sym_variants(symbol):
            urls = _build_urls(base, symbol=sym, tf_key=tf_key, tf_val=tf_val,
                               limit=int(limit), start_ms=start, end_ms=end, is_spot=is_spot)
            for url in urls:
                for attempt in range(max_retries + 1):
                    try:
                        _log(f"HTTP Bitget {market}: GET {url}")
                        data = _http_get(url, timeout=timeout)
                        # format {code,msg,data} (mix) ou liste directe (spot)
                        if isinstance(data, dict) and "code" in data and str(data["code"]) != "00000" and "data" not in data:
                            raise RuntimeError(f"Bitget error {data.get('code')}: {data.get('msg')}")
                        rows = _normalize_http_rows(data)
                        if not rows:
                            raise ValueError("Réponse vide")
                        _log(f"HTTP OK via {market} {sym} ({len(rows)} bougies) "
                             f"range=[{rows[0][0]} .. {rows[-1][0]}] (ms)")
                        return _rows_to_df(rows)
                    except (URLError, HTTPError, ValueError, KeyError, RuntimeError) as e:
                        last_err = e
                        _log(f"HTTP fail: {e} (retry {attempt}/{max_retries})")
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