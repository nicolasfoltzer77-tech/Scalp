#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

def main():
    ap = argparse.ArgumentParser(description="Agrège PnL réalisé par jour/symbole.")
    ap.add_argument("--day", default=datetime.now(timezone.utc).strftime("%Y%m%d"), help="YYYYMMDD")
    args = ap.parse_args()

    trades_path = Path("var/trades") / args.day / "trades.jsonl"
    out_dir = Path("var/reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / f"pnl_{args.day}.csv"

    if not trades_path.exists():
        print(f"Pas de trades pour {args.day} ({trades_path})")
        return 0

    agg = defaultdict(float)
    with trades_path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                evt = json.loads(line)
            except Exception:
                continue
            if evt.get("type") == "CLOSE":
                sym = evt.get("symbol", "UNKNOWN")
                agg[sym] += float(evt.get("realized_pnl_delta", 0.0))

    with out_csv.open("w", encoding="utf-8") as w:
        w.write("day,symbol,realized_pnl\n")
        for sym, pnl in sorted(agg.items()):
            w.write(f"{args.day},{sym},{pnl:.8f}\n")

    print(f"Écrit: {out_csv}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
