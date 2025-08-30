from __future__ import annotations
import csv, os, time
from typing import Dict, Any

BASE = "/opt/scalp/var/dashboard"
CSV  = f"{BASE}/signals.csv"
HEADER = ["ts", "symbol", "tf", "signal", "details"]

def append_signal(row: Dict[str, Any]) -> None:
    os.makedirs(BASE, exist_ok=True)
    write_header = not os.path.exists(CSV)
    r = {
        "ts": int(row.get("ts") or time.time()),
        "symbol": row.get("symbol", ""),
        "tf": row.get("tf", ""),
        "signal": (row.get("signal") or "HOLD").upper(),
        "details": row.get("details", ""),
    }
    with open(CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        if write_header:
            w.writeheader()
        w.writerow(r)

