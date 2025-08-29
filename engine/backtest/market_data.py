#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import pandas as pd
from datetime import datetime, timezone
from engine.adapters.bitget import BitgetClient

TF_TO_SECONDS = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}

def infer_limit(days: int, tf: str) -> int:
    sec = TF_TO_SECONDS.get(tf)
    if not sec:
        raise ValueError(f"Timeframe inconnu: {tf}")
    per_day = 86400 // sec
    return max(1, per_day * max(1, days))

def rows_to_df(rows):
    """
    Bitget OHLCV:
    [ts, open, high, low, close, baseVol, quoteVol]
    """
    if not rows:
        return pd.DataFrame(columns=[
            "timestamp","open","high","low","close","volume","quote_volume","datetime"
        ])

    cols = ["timestamp","open","high","low","close","volume","quote_volume"]
    df = pd.DataFrame(rows, columns=cols)

    # conversions
    df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce").astype("Int64")
    for c in ["open","high","low","close","volume","quote_volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df

def outfile_path(out_dir, pair, tf, fmt):
    os.makedirs(out_dir, exist_ok=True)
    ext = "csv" if fmt == "csv" else "parquet"
    return os.path.join(out_dir, f"{pair}-{tf}.{ext}")

def save_df(df, path, fmt, verbose):
    if fmt == "csv":
        df.to_csv(path, index=False)
    else:
        df.to_parquet(path, index=False)
    if verbose:
        print(f"[save] {len(df)} lignes -> {path}")

def fetch_bitget(pair, tf, days, market, verbose):
    limit = infer_limit(days, tf)
    if verbose:
        print(f"[bitget] pair={pair} tf={tf} market={market} limit={limit}")
    client = BitgetClient(market=market)
    rows = client.fetch_ohlcv(pair, tf, limit=limit)
    if verbose:
        print(f"[bitget] rows={len(rows)} first={rows[0] if rows else None}")
    return rows_to_df(rows)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pair", required=True)
    p.add_argument("--tf", default="1m")
    p.add_argument("--days", type=int, default=2)
    p.add_argument("--market", default="umcbl")
    p.add_argument("--out", dest="out_dir", default=os.environ.get("DATA_DIR","/opt/scalp_data/data"))
    p.add_argument("--format", choices=["csv","parquet"], default="csv")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    df = fetch_bitget(args.pair.upper(), args.tf, args.days, args.market.lower(), args.verbose)
    if df.empty:
        raise SystemExit(f"Aucune donnée pour {args.pair} {args.tf}")

    path = outfile_path(args.out_dir, args.pair.upper(), args.tf, args.format)
    save_df(df, path, args.format, args.verbose)

    if args.verbose:
        dt = datetime.fromtimestamp(int(df["timestamp"].iloc[0])/1000, tz=timezone.utc).isoformat()
        print(f"[done] {len(df)} lignes dès {dt} → {path}")

if __name__ == "__main__":
    main()
