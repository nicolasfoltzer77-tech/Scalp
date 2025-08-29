# -*- coding: utf-8 -*-
"""
CLI de fetch marché -> fichier local (CSV ou Parquet) pour backtests.

Exemples:
  python -m engine.backtest.market_data --pair BTCUSDT --tf 1m --days 1 --format csv
  python -m engine.backtest.market_data --pair BTCUSDT --tf 1m --days 2 --format parquet
"""

from __future__ import annotations
import os
import argparse
import sys
from datetime import datetime, timezone

import pandas as pd

from engine.adapters.bitget import BitgetClient, MAP_TF_SEC


def _ensure_dirs(path: str):
    os.makedirs(path, exist_ok=True)


def _save(df: pd.DataFrame, out_dir: str, pair: str, tf: str, fmt: str):
    _ensure_dirs(out_dir)
    base = os.path.join(out_dir, f"{pair}-{tf}")
    if fmt == "csv":
        path = base + ".csv"
        df.to_csv(path, index=False)
    else:
        path = base + ".parquet"
        df.to_parquet(path, index=False)
    print(f"[save] {len(df)} lignes -> {path}")


def load_local(data_dir: str, pair: str, tf: str) -> pd.DataFrame:
    """
    Charge BTCUSDT-1m.{csv|parquet} et normalise les colonnes.
    Retourne: timestamp, open, high, low, close, volume, quote_volume, datetime
    """
    base = os.path.join(data_dir, f"{pair}-{tf}")
    pq, csv = base + ".parquet", base + ".csv"
    if os.path.exists(pq):
        df = pd.read_parquet(pq)
    elif os.path.exists(csv):
        df = pd.read_csv(csv)
    else:
        raise FileNotFoundError(f"Aucun fichier local pour {pair}-{tf} dans {data_dir}")
    if "quote_volume" not in df.columns:
        df["quote_volume"] = pd.NA
    if "datetime" not in df.columns and "timestamp" in df.columns:
        df["datetime"] = pd.to_datetime(pd.to_numeric(df["timestamp"], errors="coerce"), unit="ms", utc=True)
    cols = ["timestamp","open","high","low","close","volume","quote_volume","datetime"]
    return df[[c for c in cols if c in df.columns]]


def parse_args(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", required=True, help="ex: BTCUSDT")
    ap.add_argument("--tf", default="1m", choices=list(MAP_TF_SEC.keys()))
    ap.add_argument("--days", type=int, default=1, help="nb de jours à récupérer")
    ap.add_argument("--market", default="umcbl", choices=["umcbl","spot"], help="bitget market (futures/spot)")
    ap.add_argument("--out", default=os.environ.get("DATA_DIR","/opt/scalp_data/data"))
    ap.add_argument("--format", default="csv", choices=["csv","parquet"])
    ap.add_argument("--verbose", action="store_true")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    limit = min(60*24*max(1, args.days), 1440)  # hard cap Bitget
    client = BitgetClient(market=args.market)

    if args.verbose:
        print(f"[bitget] pair={args.pair} tf={args.tf} market={args.market} limit={limit}")

    df = client.fetch_ohlcv_df(args.pair, timeframe=args.tf, limit=limit)
    if df.empty:
        raise RuntimeError(f"Aucune ligne reçue pour {args.pair} {args.tf} ({args.market})")

    if args.verbose:
        first = df.iloc[0].to_list()
        print(f"[bitget] rows={len(df)} first={first}")

    _save(df, args.out, args.pair, args.tf, args.format)

    if args.verbose:
        head = df.head(3)
        print(head.to_csv(index=False))


if __name__ == "__main__":
    main()
