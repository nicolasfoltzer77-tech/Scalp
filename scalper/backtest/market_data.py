from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence, Tuple
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import pandas as pd

# ============================================================================
# Logs & utilitaires
# ============================================================================
BT_DEBUG = int(os.getenv("BT_DEBUG", "0") or "0")
def _log(msg: str) -> None:
    if BT_DEBUG:
        print(f"[bt.debug] {msg}", flush=True)

def _now_ms() -> int:
    return int(time.time() * 1000)

def _tf_to_seconds(tf: str) -> int:
    tf = tf.lower().strip()
    table = {"1m":60,"3m":180,"5m":300,"15m":900,"30m":1800,"1h":3600,"4h":14400,"1d":86400}
    if tf not in table:
        raise ValueError(f"Timeframe non supporté: {tf}")
    return table[tf]

def _parse_duration(s: str) -> int:
    """
    '90s','15m','2h','3d' -> secondes
    """
    s = s.strip().lower()
    if s.endswith("s"): return int(float(s[:-1]))
    if s.endswith("m"): return int(float(s[:-1])*60)
    if s.endswith("h"): return int(float(s[:-1])*3600)
    if s.endswith("d"): return int(float(s[:-1])*86400)
    return int(float(s))  # secondes

# ============================================================================
# Politique de fraîcheur (par défaut + overrides via ENV)
# ============================================================================
def _default_max_age_seconds(tf: str) -> int:
    """
    Règles par défaut (conservatrices) :
      - 1m..15m : 2 × TF  (ex: 5m -> 10m)
      - 30m     : 1h
      - 1h      : 6h
      - 4h      : 24h
      - 1d      : 3d
    """
    tf = tf.lower()
    if tf in ("1m","3m","5m","15m"):
        return 2 * _tf_to_seconds(tf)
    if tf == "30m":
        return 3600
    if tf == "1h":
        return 6*3600
    if tf == "4h":
        return 24*3600
    if tf == "1d":
        return 3*86400
    raise ValueError(tf)

def _max_age_seconds(tf: str) -> int:
    """
    Overrides possibles (au choix) :
      - CSV_MAX_AGE_MULT=NN → NN × TF  (ex: 50 pour 1m => 50 minutes)
      - CSV_MAX_AGE_5m="45m" (prioritaire si présent)
      - CSV_MAX_AGE_DEFAULT="2h" (fallback global)
    """
    tfk = tf.lower().replace(":", "")
    env_spec = os.getenv(f"CSV_MAX_AGE_{tfk}")
    if env_spec:
        return _parse_duration(env_spec)
    mult = os.getenv("CSV_MAX_AGE_MULT")
    if mult:
        return int(float(mult) * _tf_to_seconds(tf))
    g = os.getenv("CSV_MAX_AGE_DEFAULT")
    if g:
        return _parse_duration(g)
    return _default_max_age_seconds(tf)

# ============================================================================
# CSV helpers + validation
# ============================================================================
def _data_dir(default: str = "data") -> Path:
    root = Path(os.getenv("DATA_DIR", default))
    root.mkdir(parents=True, exist_ok=True)
    return root

def _csv_path(symbol: str, timeframe: str) -> Path:
    tf = timeframe.replace(":", "")
    return _data_dir() / f"{symbol}-{tf}.csv"

def _rows_to_df(rows: Iterable[Iterable[float]]) -> pd.DataFrame:
    rows = list(rows)
    if not rows:
        raise ValueError("OHLCV vide")
    unit = "ms" if rows[0][0] > 10_000_000_000 else "s"
    df = pd.DataFrame(rows, columns=["ts","open","high","low","close","volume"])
    df["timestamp"] = pd.to_datetime(df["ts"], unit=unit, utc=True)
    return df.drop(columns=["ts"]).set_index("timestamp").sort_index()

def _read_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    # tolère quelques variations de colonnes
    cols = {c.lower(): c for c in df.columns}
    ts_col = cols.get("timestamp") or cols.get("time") or cols.get("date") or cols.get("ts")
    if not ts_col:
        raise ValueError("Colonne temps absente (timestamp/time/date/ts)")
    rename = {ts_col: "timestamp"}
    for c in ("open","high","low","close","volume"):
        if c not in cols:
            raise ValueError(f"Colonne manquante: {c}")
        rename[cols[c]] = c
    df = df.rename(columns=rename)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, infer_datetime_format=True)
    df = df[["timestamp","open","high","low","close","volume"]].sort_values("timestamp")
    df = df.drop_duplicates("timestamp")
    df = df.set_index("timestamp")
    return df

def _write_csv(path: Path, df: pd.DataFrame) -> None:
    out = df.reset_index().rename(columns={"index": "timestamp"})
    out.to_csv(path, index=False)

def _is_csv_fresh_and_valid(path: Path, timeframe: str, *, min_rows: int = 100) -> Tuple[bool, str]:
    """
    Retourne (ok, reason). ok=True si le CSV est utilisable:
      - schéma valide
      - assez de lignes
      - fraîcheur < seuil selon TF
    """
    if not path.exists():
        return False, "absent"
    try:
        df = _read_csv(path)
    except Exception as e:
        return False, f"invalid({e})"
    if len(df) < min_rows:
        return False, f"too_few_rows({len(df)}<{min_rows})"
    # Fraîcheur
    last_ts = int(df.index.max().timestamp())
    age_s = int(time.time()) - last_ts
    max_age = _max_age_seconds(timeframe)
    if age_s > max_age:
        return False, f"stale({age_s}s>{max_age}s)"
    # Monotonicité (échantillon)
    if not df.index.is_monotonic_increasing:
        return False, "not_monotonic"
    return True, "ok"

# ============================================================================
# Fallback réseau (CCXT d'abord, HTTP sinon)
# ============================================================================
def _ensure_ccxt() -> Any | None:
    try:
        import ccxt  # type: ignore
        return ccxt
    except Exception:
        return None

def _fetch_via_ccxt(symbol: str, timeframe: str, limit: int = 1000) -> Optional[pd.DataFrame]:
    ccxt = _ensure_ccxt()
    if not ccxt:
        _log("ccxt indisponible")
        return None
    ex = ccxt.bitget({"enableRateLimit": True, "options": {"defaultType": "swap"}})
    ex.load_markets()
    base = symbol.upper()
    if not base.endswith("USDT"):
        raise ValueError("symbol doit finir par USDT (ex: BTCUSDT)")
    coin = base[:-4]
    candidates = [f"{coin}/USDT:USDT", f"{coin}/USDT"]  # perp puis spot
    for ccxt_sym in candidates:
        try:
            rows = ex.fetch_ohlcv(ccxt_sym, timeframe=timeframe, limit=limit)
            if rows:
                return _rows_to_df(sorted(rows, key=lambda r: r[0]))
        except Exception as e:
            _log(f"ccxt fail {ccxt_sym}: {e}")
            continue
    return None

# === (facultatif) HTTP Bitget v1 minimal ===
_GRAN_MIX = {"1m":"1min","3m":"3min","5m":"5min","15m":"15min","30m":"30min","1h":"1h","4h":"4h","1d":"1day"}
_PERIOD_SPOT = {"1m":"1min","3m":"3min","5m":"5min","15m":"15min","30m":"30min","1h":"1hour","4h":"4hour","1d":"1day"}

def _http_get(url: str, timeout: int = 20) -> dict | list:
    req = Request(url, headers={"User-Agent":"backtest-marketdata/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def _normalize_http_rows(payload: dict | list) -> list[list[float]]:
    rows = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError(f"Réponse inattendue: {payload}")
    out = []
    for r in rows:
        ts = int(str(r[0])); o,h,l,c,v = map(float,(r[1],r[2],r[3],r[4],r[5]))
        out.append([ts,o,h,l,c,v])
    out.sort(key=lambda x:x[0])
    return out

def _fetch_via_http(symbol: str, timeframe: str, limit: int = 1000) -> Optional[pd.DataFrame]:
    tf = timeframe.lower()
    g = _GRAN_MIX.get(tf); p = _PERIOD_SPOT.get(tf)
    if not (g and p):
        return None
    # mix umcbl puis spot spbl, paramètres minimum (v1)
    trials = [
        f"https://api.bitget.com/api/mix/v1/market/candles?symbol={symbol}_UMCBL&granularity={g}&limit={limit}",
        f"https://api/bitget.com/api/mix/v1/market/candles?symbol={symbol}&granularity={g}&limit={limit}",
        f"https://api.bitget.com/api/spot/v1/market/candles?symbol={symbol}_SPBL&period={p}&limit={limit}",
        f"https://api.bitget.com/api/spot/v1/market/candles?symbol={symbol}&period={p}&limit={limit}",
    ]
    for url in trials:
        try:
            payload = _http_get(url)
            if isinstance(payload, dict) and "code" in payload and str(payload["code"]) != "00000" and "data" not in payload:
                raise RuntimeError(f"Bitget error {payload.get('code')}: {payload.get('msg')}")
            rows = _normalize_http_rows(payload)
            if rows:
                return _rows_to_df(rows)
        except Exception as e:
            _log(f"HTTP fail: {url} -> {e}")
            continue
    return None

# ============================================================================
# API publique utilisée par l’orchestrateur/backtest
# ============================================================================
def fetch_ohlcv_best(symbol: str, timeframe: str, *, limit: int = 1000) -> pd.DataFrame:
    """
    Tente d’abord CCXT (si présent), sinon HTTP v1. Lève si tout échoue.
    """
    df = _fetch_via_ccxt(symbol, timeframe, limit=limit)
    if df is not None:
        _log(f"source=ccxt  n={len(df)}")
        return df
    df = _fetch_via_http(symbol, timeframe, limit=limit)
    if df is not None:
        _log(f"source=http  n={len(df)}")
        return df
    raise RuntimeError(f"Aucune source OHLCV pour {symbol} {timeframe}")

def hybrid_loader(
    data_dir: str = "data",
    *,
    use_cache_first: bool = True,
    min_rows: int = 100,
    refill_if_stale: bool = True,
    network_limit: int = 1000,
):
    """
    Loader smart :
      1) si CSV présent ET frais/valide → le renvoie
      2) sinon, si refill_if_stale → recharge (CCXT>HTTP) puis écrit CSV
      3) sinon → lève
    """
    os.environ.setdefault("DATA_DIR", data_dir)

    def load(symbol: str, timeframe: str, start: str | None, end: str | None) -> pd.DataFrame:
        path = _csv_path(symbol, timeframe)

        if use_cache_first:
            ok, why = _is_csv_fresh_and_valid(path, timeframe, min_rows=min_rows)
            if ok:
                _log(f"CSV OK: {path}")
                df = _read_csv(path)
            else:
                _log(f"CSV non utilisable ({why}): {path}")
                if not refill_if_stale:
                    raise RuntimeError(f"CSV invalide et recharge désactivée: {path} ({why})")
                df = fetch_ohlcv_best(symbol, timeframe, limit=network_limit)
                _write_csv(path, df)
        else:
            df = fetch_ohlcv_best(symbol, timeframe, limit=network_limit)
            _write_csv(path, df)

        # Fenêtrage temporel si demandé (timestamps UTC)
        if start:
            df = df.loc[pd.Timestamp(start, tz="UTC") :]
        if end:
            df = df.loc[: pd.Timestamp(end, tz="UTC")]
        return df

    return load