# scalper/backtest/runner.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Dict, Optional

import pandas as pd

from .engine import run_single, OHLCVLoader
from .market_data import fetch_ohlcv_bitget, BitgetConfig


def csv_loader_factory(data_dir: str) -> OHLCVLoader:
    """Ancien loader: CSV obligatoire dans data_dir."""
    root = Path(data_dir)

    def load(symbol: str, timeframe: str, start: str | None, end: str | None) -> pd.DataFrame:
        tf = timeframe.replace(":", "")
        path = root / f"{symbol}-{tf}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Fichier introuvable: {path}")
        df = pd.read_csv(path)
        ts_col = next((c for c in df.columns if c.lower() in ("ts", "timestamp", "time", "date")), None)
        if ts_col is None:
            raise ValueError("Colonne temps introuvable (timestamp/time/date)")
        df = df.rename(columns={ts_col: "timestamp"})
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, infer_datetime_format=True)
        df = df.set_index("timestamp").sort_index()
        if start:
            df = df.loc[pd.Timestamp(start, tz="UTC") :]
        if end:
            df = df.loc[: pd.Timestamp(end, tz="UTC")]
        return df

    return load


def hybrid_loader_factory(
    data_dir: str,
    *,
    use_api: bool = True,
    market: str = "mix",
    api_limit: int = 1000,
) -> OHLCVLoader:
    """
    Loader hybride :
      1) essaie de lire `data/<SYMBOL>-<TF>.csv`
      2) sinon, si `use_api`, télécharge depuis Bitget (public), sauvegarde le CSV, et renvoie le DF
    """
    root = Path(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    cfg = BitgetConfig(market=market)

    def load(symbol: str, timeframe: str, start: str | None, end: str | None) -> pd.DataFrame:
        tf = timeframe.replace(":", "")
        path = root / f"{symbol}-{tf}.csv"
        if path.exists():
            df = pd.read_csv(path)
            ts_col = next((c for c in df.columns if c.lower() in ("ts", "timestamp", "time", "date")), None)
            if ts_col is None:
                raise ValueError("Colonne temps introuvable (timestamp/time/date)")
            df = df.rename(columns={ts_col: "timestamp"})
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, infer_datetime_format=True)
            df = df.set_index("timestamp").sort_index()
        else:
            if not use_api:
                raise FileNotFoundError(f"Fichier introuvable: {path}")
            # — API Bitget —
            df = fetch_ohlcv_bitget(symbol, timeframe, limit=api_limit, cfg=cfg)
            # persister en CSV pour usage ultérieur
            tmp = df.reset_index().rename(columns={"timestamp": "timestamp"})
            tmp.to_csv(path, index=False)

        # Découpe temporelle
        if start:
            df = df.loc[pd.Timestamp(start, tz="UTC") :]
        if end:
            df = df.loc[: pd.Timestamp(end, tz="UTC")]
        return df

    return load


def run_multi(
    *,
    symbols: Iterable[str],
    timeframes: Iterable[str],
    loader: OHLCVLoader,
    out_dir: str = "backtests",
    initial_cash: float = 10_000.0,
    risk_pct: float = 0.005,
    slippage_bps: float = 1.5,
) -> Dict[str, Dict[str, Dict]]:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    results: Dict[str, Dict[str, Dict]] = {}

    for sym in symbols:
        results[sym] = {}
        for tf in timeframes:
            res = run_single(
                symbol=sym,
                timeframe=tf,
                loader=loader,
                initial_cash=initial_cash,
                risk_pct=risk_pct,
                slippage_bps=slippage_bps,
            )
            base = Path(out_dir) / f"{sym}_{tf}"
            res["equity_curve"].to_csv(base.with_suffix(".equity_curve.csv"), index=False)
            res["trades"].to_csv(base.with_suffix(".trades.csv"), index=False)
            res["fills"].to_csv(base.with_suffix(".fills.csv"), index=False)
            with open(base.with_suffix(".metrics.json"), "w", encoding="utf-8") as fh:
                json.dump(res["metrics"], fh, ensure_ascii=False, indent=2)
            results[sym][tf] = res

    # résumé global
    summary_rows = []
    for sym, tfs in results.items():
        for tf, res in tfs.items():
            m = res["metrics"]
            summary_rows.append(
                {
                    "symbol": sym,
                    "timeframe": tf,
                    "return_pct": m["return_pct"],
                    "n_trades": m["n_trades"],
                    "win_rate_pct": m["win_rate_pct"],
                    "max_dd_pct": m["max_dd_pct"],
                }
            )
    pd.DataFrame(summary_rows).sort_values(["symbol", "timeframe"]).to_csv(
        Path(out_dir) / "summary.csv", index=False
    )
    return results