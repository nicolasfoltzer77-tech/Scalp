# -*- coding: utf-8 -*-
from __future__ import annotations
import os, argparse
import pandas as pd
from engine.adapters.bitget import BitgetClient, MAP_TF_SEC, MAX_LIMIT

def _ensure_dirs(p): os.makedirs(p, exist_ok=True)

def _save(df, out_dir, pair, tf, fmt):
    _ensure_dirs(out_dir)
    base = os.path.join(out_dir, f"{pair}-{tf}")
    path = base + (".csv" if fmt=="csv" else ".parquet")
    (df.to_csv if fmt=="csv" else df.to_parquet)(path, index=False)
    print(f"[save] {len(df)} lignes -> {path}")

def parse_args(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", required=True)
    ap.add_argument("--tf", default="1m", choices=list(MAP_TF_SEC.keys()))
    ap.add_argument("--days", type=int, default=1)
    ap.add_argument("--market", default="umcbl", choices=["umcbl","spot"])
    ap.add_argument("--out", default=os.environ.get("DATA_DIR","/opt/scalp_data/data"))
    ap.add_argument("--format", default="csv", choices=["csv","parquet"])
    ap.add_argument("--verbose", action="store_true")
    return ap.parse_args(argv)

def main(argv=None):
    a = parse_args(argv)
    # Bitget: limite stricte 1000 -> on cappe
    wanted = 60*24*max(1, a.days)
    cap = MAX_LIMIT.get(a.market, 1000)
    limit = min(wanted, cap)
    cli = BitgetClient(market=a.market)
    if a.verbose:
        print(f"[bitget] pair={a.pair} tf={a.tf} market={a.market} limit={limit}")
    df = cli.fetch_ohlcv_df(a.pair, a.tf, limit=limit)
    if df.empty: raise RuntimeError(f"Aucune donnée reçue pour {a.pair} {a.tf} ({a.market})")
    _save(df, a.out, a.pair, a.tf, a.format)
    if a.verbose:
        print(df.head(3).to_csv(index=False))

if __name__ == "__main__":
    main()
