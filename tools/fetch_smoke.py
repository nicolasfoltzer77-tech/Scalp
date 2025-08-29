#!/usr/bin/env python3
from __future__ import annotations
import os
from engine.backtest.market_data import hybrid_loader

def main():
    # 1) Où écrire les CSV
    data_dir = os.environ.get("DATA_DIR", "/notebooks/scalp_data/data")
    # 2) Fabrique un loader qui crée/rafraîchit le CSV si besoin
    load = hybrid_loader(data_dir=data_dir, use_cache_first=True, refill_if_stale=True, network_limit=1500)
    # 3) Charge 2 jours de 1m
    df = load("BTCUSDT", "1m", start=None, end=None)
    print(f"[ok] BTCUSDT 1m -> rows={len(df):,} path={data_dir}/BTCUSDT-1m.csv")

if __name__ == "__main__":
    main()
