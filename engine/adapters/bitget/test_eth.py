from __future__ import annotations
from engine.adapters.bitget.client import BitgetClient

def main() -> None:
    # unified-margin coin-margined futures
    c = BitgetClient(market="umcbl")
    rows = c.fetch_ohlcv("ETHUSDT", "1m", limit=5)
    print("rows:", len(rows))
    print("first:", rows[0] if rows else None)
    print("last :", rows[-1] if rows else None)

if __name__ == "__main__":
    main()
