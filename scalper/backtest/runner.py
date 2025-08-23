from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

import pandas as pd

from scalper.backtest.engine import run_single, OHLCVLoader

# ==== Loader OHLCV par défaut ================================================
# Tu peux brancher ici ton adapter maison (ccxt, Bitget CSV, Parquet local, etc.)
def csv_loader_factory(data_dir: str) -> OHLCVLoader:
    root = Path(data_dir)

    def load(symbol: str, timeframe: str, start: str | None, end: str | None) -> pd.DataFrame:
        # Exemple: data/BTCUSDT-1m.csv ; colonnes: timestamp,open,high,low,close,volume
        # Adapte si tu as d'autres noms de fichiers
        tf = timeframe.replace(":", "")
        path = root / f"{symbol}-{tf}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Fichier introuvable: {path}")
        df = pd.read_csv(path)
        # normalisation
        ts_col = next((c for c in df.columns if c.lower() in ("ts", "timestamp", "time", "date")), None)
        if ts_col is None:
            raise ValueError("Colonne temps introuvable")
        df = df.rename(columns={ts_col: "timestamp"})
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, infer_datetime_format=True)
        df = df.set_index("timestamp").sort_index()
        # slice temporel si demandé
        if start:
            df = df.loc[pd.Timestamp(start, tz="UTC") :]
        if end:
            df = df.loc[: pd.Timestamp(end, tz="UTC")]
        return df

    return load


# ==== Run multi ==============================================================
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
    """
    Lance un backtest **multi symboles / multi timeframes** et écrit
    `equity_curve.csv`, `trades.csv`, `fills.csv`, `metrics.json` par combinaison.
    Retourne un dict {symbol: {tf: result}} où result = sortie run_single.
    """
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
            # sauvegarde
            base = Path(out_dir) / f"{sym}_{tf}"
            base.parent.mkdir(parents=True, exist_ok=True)
            res["equity_curve"].to_csv(base.with_suffix(".equity_curve.csv"), index=False)
            res["trades"].to_csv(base.with_suffix(".trades.csv"), index=False)
            res["fills"].to_csv(base.with_suffix(".fills.csv"), index=False)
            with open(base.with_suffix(".metrics.json"), "w", encoding="utf-8") as fh:
                json.dump(res["metrics"], fh, ensure_ascii=False, indent=2)
            results[sym][tf] = res

    # tableau récapitulatif pour choisir une config
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