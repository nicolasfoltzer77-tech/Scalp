#!/usr/bin/env python3
import os
from engine.backtest.market_data import hybrid_loader

def main():
    data_dir = os.environ.get("DATA_DIR", "/opt/scalp_data/data")
    os.makedirs(data_dir, exist_ok=True)

    load = hybrid_loader(
        data_dir=data_dir,
        use_cache_first=True,
        refill_if_stale=True,
        network_limit=1500,
    )

    df = load("BTCUSDT", "1m", start=None, end=None)
    print(f"[ok] BTCUSDT 1m -> {len(df):,} rows -> {data_dir}/BTCUSDT-1m.csv")

if __name__ == "__main__":
    main()
