from engine.adapters.bitget import BitgetClient
from pathlib import Path

def run(pair="BTCUSDT", tf="1m", limit=1440, market="umcbl", out="/opt/scalp_data/data"):
    c = BitgetClient(market=market)
    df = c.fetch_ohlcv_df(pair, tf, limit)
    Path(out).mkdir(parents=True, exist_ok=True)
    f = Path(out) / f"{pair}-{tf}.csv"
    df.to_csv(f, index=False)
    print(f"[save] {len(df)} -> {f}")

if __name__ == "__main__":
    for pair in ("BTCUSDT","ETHUSDT"):
        run(pair, "1m", 1440, market="umcbl")

