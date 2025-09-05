from __future__ import annotations
import csv, os, time
from typing import Dict, Any

BASE = "/opt/scalp/var/dashboard"
CSV  = f"{BASE}/signals_f.csv"
HEADER = [
    "ts","symbol","tf","signal",
    "rsi","ema","sma","factor",
    "why"  # court texte synthétique si besoin
]

def append_signal_factored(row: Dict[str, Any]) -> None:
    os.makedirs(BASE, exist_ok=True)
    write_header = not os.path.exists(CSV)

    def _num(x, default=""):
        try:
            if x is None or x == "":
                return default
            return float(x)
        except Exception:
            return default

    r = {
        "ts": int(row.get("ts") or time.time()),
        "symbol": str(row.get("symbol","")),
        "tf": str(row.get("tf","")),
        "signal": str(row.get("signal","HOLD")).upper(),
        "rsi": _num(row.get("rsi")),
        "ema": _num(row.get("ema")),
        "sma": _num(row.get("sma")),
        "factor": _num(row.get("factor")),
        "why": str(row.get("why",""))[:200],
    }

    with open(CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        if write_header:
            w.writeheader()
        w.writerow(r)
