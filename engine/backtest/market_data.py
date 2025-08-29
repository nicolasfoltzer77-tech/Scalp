# -*- coding: utf-8 -*-
"""
CLI simple pour récupérer des OHLCV normalisés
et écrire un CSV exploitable par le moteur.
"""
from __future__ import annotations
import argparse
from pathlib import Path

from engine.adapters.bitget import BitgetClient


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--provider", default="bitget", choices=["bitget"])
    p.add_argument("--market", default="umcbl", help="umcbl (futures) ou spbl (spot)")
    p.add_argument("--pair", required=True, help="ex: BTCUSDT")
    p.add_argument("--tf", default="1m")
    p.add_argument("--limit", type=int, default=1000)
    p.add_argument("--out", default=".")
    p.add_argument("--format", default="csv", choices=["csv", "parquet"])
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    if args.provider != "bitget":
        raise SystemExit("Pour l’instant seul --provider bitget est supporté ici")

    client = BitgetClient(market=args.market)

    rows = client.fetch_ohlcv(args.pair, args.tf, args.limit)
    if args.verbose:
        print(f"[bitget] pair={args.pair} tf={args.tf} market={args.market} rows={len(rows)}")
        if rows:
            print("[bitget] first=", rows[0])

    df = client.fetch_ohlcv_df(args.pair, args.tf, args.limit)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{args.pair}-{args.tf}.csv"

    if args.format == "csv":
        df.to_csv(out_file, index=False)
    else:
        out_file = out_file.with_suffix(".parquet")
        df.to_parquet(out_file, index=False)

    print("[save]", len(df), "lignes ->", out_file)


if __name__ == "__main__":
    main()
