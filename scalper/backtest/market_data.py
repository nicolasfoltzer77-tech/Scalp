# scalper/backtest/market_data.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable, Optional

import pandas as pd

BT_DEBUG = int(os.getenv("BT_DEBUG", "0") or "0")


# -----------------------------------------------------------------------------
# Logging debug
# -----------------------------------------------------------------------------
def _log(msg: str) -> None:
    if BT_DEBUG:
        print(f"[bt.debug] {msg}", flush=True)


# -----------------------------------------------------------------------------
# Utilitaires CSV
# -----------------------------------------------------------------------------
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


# -----------------------------------------------------------------------------
# Normalisation OHLCV → DataFrame
# -----------------------------------------------------------------------------
def _rows_to_df(rows: Iterable[Iterable[float]]) -> pd.DataFrame:
    rows = list(rows)
    if not rows:
        raise ValueError("OHLCV vide")
    # ts en s ou ms
    unit = "ms" if rows[0][0] > 10_000_000_000 else "s"
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["ts"], unit=unit, utc=True)
    df = df.drop(columns=["ts"]).set_index("timestamp").sort_index()
    _log(f"→ OHLCV normalisé: n={len(df)}, t0={df.index.min()}, t1={df.index.max()}")
    return df


# -----------------------------------------------------------------------------
# 1) Source: exchange.fetch_ohlcv (si présent)
# -----------------------------------------------------------------------------
def fetch_ohlcv_via_exchange(exchange: Any, symbol: str, timeframe: str, *, limit: int = 1000) -> pd.DataFrame:
    if not hasattr(exchange, "fetch_ohlcv"):
        raise AttributeError("exchange.fetch_ohlcv introuvable")
    _log(f"fetch via exchange.fetch_ohlcv: symbol={symbol} tf={timeframe} limit={limit}")
    rows = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)  # sync ou adapté par ton wrapper
    return _rows_to_df(rows)


# -----------------------------------------------------------------------------
# 2) Source: CCXT Bitget (fallback universel)
# -----------------------------------------------------------------------------
def _ensure_ccxt() -> "ccxt.bitget":
    try:
        import ccxt  # type: ignore
    except Exception as e:
        raise RuntimeError("CCXT n'est pas installé. `pip install ccxt`") from e
    return ccxt.bitget()


def _ccxt_symbol_variants(symbol: str, market_hint: Optional[str]) -> list[str]:
    """Génère des tentatives de mapping symbol → CCXT."""
    s = symbol.upper()
    # BTCUSDT → BTC/USDT (spot)
    spot = s.replace("USDT", "/USDT")
    # BTCUSDT → BTC/USDT:USDT (perp USDT-M)
    swap = s.replace("USDT", "/USDT:USDT")
    out: list[str] = []
    if (market_hint or "").lower() == "mix":
        out = [swap, spot]
    elif (market_hint or "").lower() == "spot":
        out = [spot, swap]
    else:
        out = [spot, swap]
    # garder unique
    seen, uniq = set(), []
    for x in out:
        if x not in seen:
            seen.add(x); uniq.append(x)
    return uniq


def fetch_ohlcv_via_ccxt(
    symbol: str,
    timeframe: str,
    *,
    limit: int = 1000,
    market_hint: Optional[str] = None,
) -> pd.DataFrame:
    ex = _ensure_ccxt()
    ex.load_markets()
    candidates = _ccxt_symbol_variants(symbol, market_hint)
    _log(f"CCXT: essais symboles {candidates} tf={timeframe} limit={limit}")
    last_err: Optional[Exception] = None
    for sym in candidates:
        try:
            rows = ex.fetch_ohlcv(sym, timeframe=timeframe, limit=limit)
            _log(f"CCXT OK: {sym} (n={len(rows)})")
            return _rows_to_df(rows)
        except Exception as e:
            last_err = e
            _log(f"CCXT fail {sym}: {e}")
            continue
    raise last_err or RuntimeError("CCXT Bitget: impossible d'obtenir l'OHLCV")


# -----------------------------------------------------------------------------
# Loader hybride : CSV → exchange → CCXT, avec cache CSV
# -----------------------------------------------------------------------------
def hybrid_loader(
    data_dir: str = "data",
    *,
    exchange: Any | None = None,
    market_hint: Optional[str] = None,  # "spot" | "mix" (futures) | None
    api_limit: int = 1000,
):
    """
    1) lit data/<SYMBOL>-<TF>.csv si présent,
    2) sinon via exchange.fetch_ohlcv (si fourni),
    3) sinon via CCXT Bitget,
    puis écrit le CSV en cache.
    """
    def load(symbol: str, timeframe: str, start: str | None, end: str | None) -> pd.DataFrame:
        path = _csv_path(data_dir, symbol, timeframe)
        src = "csv"
        if path.exists():
            df = _read_csv(path)
        else:
            # exchange
            if exchange is not None:
                try:
                    df = fetch_ohlcv_via_exchange(exchange, symbol, timeframe, limit=api_limit)
                    src = "exchange"
                except Exception as e:
                    _log(f"fallback CCXT (exchange KO): {e}")
                    df = fetch_ohlcv_via_ccxt(symbol, timeframe, limit=api_limit, market_hint=market_hint)
                    src = "ccxt"
            else:
                df = fetch_ohlcv_via_ccxt(symbol, timeframe, limit=api_limit, market_hint=market_hint)
                src = "ccxt"
            _write_csv(path, df)

        if start:
            df = df.loc[pd.Timestamp(start, tz="UTC") :]
        if end:
            df = df.loc[: pd.Timestamp(end, tz="UTC")]
        _log(f"loader -> {symbol} {timeframe} (src={src}) n={len(df)} "
             f"range=[{df.index.min()} .. {df.index.max()}]")
        return df

    return load


# -----------------------------------------------------------------------------
# Compat historique (utilisée par backtest_telegram)
# -----------------------------------------------------------------------------
def hybrid_loader_from_exchange(
    exchange: Any,
    data_dir: str = "data",
    *,
    api_limit: int = 1000,
):
    """Signature historique : garde le même comportement (CSV → exchange → CCXT)."""
    return hybrid_loader(
        data_dir=data_dir,
        exchange=exchange,
        market_hint=None,
        api_limit=api_limit,
    )