#!/usr/bin/env python3
from __future__ import annotations
import argparse, os, time
from pathlib import Path
from engine.config.loader import load_config
from engine.exchange.bitget_rest import BitgetFuturesClient
from engine.pairs.selector import select_top_pairs
from engine.config.watchlist import save_watchlist
from engine.backtest.loader_csv import write_csv_ohlcv
#!/usr/bin/env python3
# jobs/refresh_pairs.py

# --- bootstrap chemin + sitecustomize ---
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
try:
    import sitecustomize  # charge .env + deps + paths
except Exception:
    pass
# --- fin bootstrap ---

def main() -> int:
    ap = argparse.ArgumentParser(description="Sélection dynamique des paires + backfill")
    ap.add_argument("--universe", default="", help="Liste de symboles à considérer (sinon auto)")
    ap.add_argument("--timeframe", default="5m")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--backfill-tfs", default="1m,5m,15m,1h", help="TF à stocker pour backtests")
    ap.add_argument("--limit", type=int, default=2000, help="bougies par TF")
    args = ap.parse_args()

    cfg = load_config()
    client = BitgetFuturesClient(
        access_key=cfg["secrets"]["bitget"]["access"],
        secret_key=cfg["secrets"]["bitget"]["secret"],
        passphrase=cfg["secrets"]["bitget"]["passphrase"],
        base_url=os.getenv("BITGET_BASE_URL","https://api.bitget.com"),
    )

    universe = [s.strip() for s in args.universe.split(",") if s.strip()] or None
    top = select_top_pairs(client, universe=universe, timeframe=args.timeframe, top_n=int(args.top))
    wl_path = save_watchlist(top)
    print(f"[✓] Watchlist ({len(top)}) écrite -> {wl_path}")

    # Backfill pour ces paires sur les TF demandés
    data_dir = Path(cfg["runtime"]["data_dir"])
    tfs = [t.strip() for t in args.backfill_tfs.split(",") if t.strip()]
    for item in top:
        for tf in tfs:
            resp = client.get_klines(item.symbol, interval=tf, limit=args.limit)
            rows = resp.get("data") or []
            write_csv_ohlcv(data_dir, item.symbol, tf, rows)
            print(f"[↓] {item.symbol} {tf} -> {data_dir}")
    print("[✓] Refresh pairs + backfill terminé.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())