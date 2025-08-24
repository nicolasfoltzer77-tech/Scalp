from __future__ import annotations
import argparse, os
from pathlib import Path
from engine.config.loader import load_config
from engine.exchange.bitget_rest import BitgetFuturesClient
from engine.backtest.loader_csv import write_csv_ohlcv

def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill OHLCV -> DATA_ROOT/data")
    ap.add_argument("--symbols", required=True, help="BTCUSDT,ETHUSDT")
    ap.add_argument("--tfs", required=True, help="1m,5m,15m,1h")
    ap.add_argument("--limit", type=int, default=5000)
    args = ap.parse_args()

    cfg = load_config()
    out_dir = Path(cfg["runtime"]["data_dir"]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    client = BitgetFuturesClient(
        access_key=cfg["secrets"]["bitget"]["access"],
        secret_key=cfg["secrets"]["bitget"]["secret"],
        passphrase=cfg["secrets"]["bitget"]["passphrase"],
        base_url=os.getenv("BITGET_BASE_URL","https://api.bitget.com"),
    )

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    tfs = [t.strip() for t in args.tfs.split(",") if t.strip()]
    for sym in symbols:
        for tf in tfs:
            resp = client.get_klines(sym, interval=tf, limit=args.limit)
            rows = resp.get("data") or []
            write_csv_ohlcv(out_dir, sym, tf, rows)
            print(f"[✓] {sym} {tf} -> {out_dir}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())