#!/usr/bin/env python3
from __future__ import annotations
import os, time, json, re
from typing import Dict, List

KLINES_DIR = "/opt/scalp/data/klines"
OUT_JSON   = "/opt/scalp/var/dashboard/data_status.json"

# TFs pris en charge (ajoute/enlève si besoin)
TFS = ["1m","5m","15m","1h","4h","1d"]

FRESH_MAX = { "1m":30, "5m":150, "15m":450, "1h":1800, "4h":7200, "1d":7200 }      # 1d ~ 2h
STALE_MAX = { "1m":120,"5m":600, "15m":1800,"1h":7200,"4h":21600,"1d":10800 }      # 1d ~ 3h

SYMBOL_RE = re.compile(r"^([A-Z0-9]+)USDT_([a-z0-9]+)\.csv$")

def status_from_age(tf: str, age: float) -> str:
    if age <= FRESH_MAX.get(tf, 60):
        return "fresh"
    if age <= STALE_MAX.get(tf, 600):
        return "reloading"
    return "stale"

def list_symbols() -> List[str]:
    if not os.path.isdir(KLINES_DIR):
        return []
    syms = set()
    for name in os.listdir(KLINES_DIR):
        m = SYMBOL_RE.match(name)
        if not m: 
            continue
        sym, tf = m.group(1), m.group(2)
        if tf in TFS:
            syms.add(sym)  # sans USDT
    return sorted(syms)

def klines_path(sym: str, tf: str) -> str:
    return os.path.join(KLINES_DIR, f"{sym}USDT_{tf}.csv")

def build() -> Dict:
    now = time.time()
    items = []
    syms = list_symbols()
    for sym in syms:
        tfs_map = {}
        for tf in TFS:
            path = klines_path(sym, tf)
            if not os.path.exists(path):
                tfs_map[tf] = {"status":"absent", "age_sec": None}
                continue
            age = max(0, int(now - os.path.getmtime(path)))
            tfs_map[tf] = {"status": status_from_age(tf, age), "age_sec": age}
        items.append({"symbol": sym, "tfs": tfs_map})
    payload = {"updated_at": int(now), "tfs": TFS, "items": items}
    return payload

def main():
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    data = build()
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"Wrote {OUT_JSON} with {len(data.get('items',[]))} symbols.")

if __name__ == "__main__":
    main()
