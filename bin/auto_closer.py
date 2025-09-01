#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, uuid
from pathlib import Path
from datetime import datetime, timezone
from engine.position_tracker import PositionTracker

def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def load_open_positions(day: str) -> list[dict]:
    pos_path = Path("var/positions") / day / "positions.jsonl"
    if not pos_path.exists():
        return []
    opened = []
    with pos_path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                evt = json.loads(line)
            except Exception:
                continue
            if evt.get("status") == "OPEN":
                opened.append(evt)
    return opened

def main():
    ap = argparse.ArgumentParser(description="Auto-close positions on SL/TP or timeout.")
    ap.add_argument("--day", default=datetime.now(timezone.utc).strftime("%Y%m%d"))
    ap.add_argument("--price", type=float, required=True, help="prix courant (mock)")
    args = ap.parse_args()

    opened = load_open_positions(args.day)
    if not opened:
        print("Pas de positions ouvertes.")
        return 0

    tracker = PositionTracker()
    for pos in opened:
        side = pos["side"]
        entry = pos["entry_price"]
        qty = pos["qty"]
        sl = pos["sl"]
        tp1 = pos.get("tp1")
        tp2 = pos.get("tp2")

        close_price = None
        if side == "LONG":
            if args.price <= sl:
                close_price = sl
            elif tp1 and args.price >= tp1:
                close_price = tp1
        elif side == "SHORT":
            if args.price >= sl:
                close_price = sl
            elif tp1 and args.price <= tp1:
                close_price = tp1

        if close_price:
            print(f"Clôture {pos['symbol']} {side} à {close_price}")
            tracker.close(
                position_id=pos["position_id"],
                entry_price=entry,
                close_price=close_price,
                qty=qty,
                side=side,
            )

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
