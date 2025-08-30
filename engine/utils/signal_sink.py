from __future__ import annotations
import csv, os, time
from typing import Dict, Any

CSV_PATH = "/opt/scalp/var/dashboard/signals.csv"

HEADER = ["ts","symbol","tf","signal","details"]

def _ensure_dir(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)

def append_signal(row: Dict[str, Any]):
    """row keys: symbol, tf, signal, details (str)"""
    _ensure_dir(CSV_PATH)
    new_file = not os.path.exists(CSV_PATH)
    try:
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new_file:
                w.writerow(HEADER)
            w.writerow([
                int(time.time()),
                row.get("symbol",""),
                row.get("tf",""),
                row.get("signal","HOLD"),
                row.get("details",""),
            ])
    except Exception:
        # jamais bloquer le bot pour ça
        pass
