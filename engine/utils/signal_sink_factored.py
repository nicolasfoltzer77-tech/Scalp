#!/usr/bin/env python3
from __future__ import annotations
import csv, os, time
from typing import Dict, Any

BASE = "/opt/scalp/var/dashboard"
CSVF = f"{BASE}/signals_f.csv"
HEADER = [
    "ts","symbol","tf","side","score",
    "rsi_value","rsi_factor",
    "sma_fast_factor",
    "ema_trend_slope","ema_trend_factor",
    "notes",
]

def _ensure_header(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(HEADER)

def append_signal_factored(row: Dict[str, Any]) -> None:
    """
    row keys attendus:
      ts?, symbol, tf, side, score,
      rsi_value?, rsi_factor,
      sma_fast_factor,
      ema_trend_slope?, ema_trend_factor,
      notes?
    """
    _ensure_header(CSVF)
    out = {
        "ts": int(row.get("ts") or time.time()),
        "symbol": str(row.get("symbol","")).strip(),
        "tf": str(row.get("tf","")).strip(),
        "side": str(row.get("side","HOLD")).upper().strip(),
        "score": int(row.get("score") or 0),
        "rsi_value": "" if row.get("rsi_value") is None else row.get("rsi_value"),
        "rsi_factor": int(row.get("rsi_factor") or 0),
        "sma_fast_factor": int(row.get("sma_fast_factor") or 0),
        "ema_trend_slope": "" if row.get("ema_trend_slope") is None else row.get("ema_trend_slope"),
        "ema_trend_factor": int(row.get("ema_trend_factor") or 0),
        "notes": str(row.get("notes",""))[:160],
    }
    with open(CSVF, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=HEADER).writerow(out)
