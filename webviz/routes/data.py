from __future__ import annotations
import os, csv, time, math, glob
from pathlib import Path
from typing import Dict, Any, List, Tuple
from fastapi import APIRouter

router = APIRouter()

BASE = "/opt/scalp"
KLINES_DIR = f"{BASE}/data/klines"
CONF = f"{BASE}/config/indicators.yml"
LOCKS = f"{BASE}/var/locks"

TF_SEC = {"1m":60, "5m":300, "15m":900}

def load_yaml(path: str) -> Dict[str, Any]:
    import yaml
    if not os.path.exists(path): return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def parse_name(p: str) -> Tuple[str,str]:
    # /opt/scalp/data/klines/BTCUSDT_1m.csv -> BTCUSDT, 1m
    b = os.path.basename(p)
    name = b[:-4]
    sym, tf = name.rsplit("_", 1)
    return sym, tf

def last_row_ts(path: str) -> int | None:
    try:
        last = None
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.reader(f):
                if not row: continue
                try:
                    last = int(float(row[0]))
                except Exception:
                    continue
        return last
    except FileNotFoundError:
        return None

def status_for(age: int, max_age: int, locked: bool) -> str:
    if locked:                # backfill en cours
        return "orange"
    if age < 0 or max_age <= 0:
        return "grey"
    if age <= max_age:        # frais
        return "green"
    if age <= max_age * 5:    # un peu vieux -> en cours de recharge probable
        return "orange"
    return "red"              # trop vieux

@router.get("/api/data_status")
def data_status() -> Dict[str, Any]:
    cfg = load_yaml(CONF)
    fresh = cfg.get("freshness_max_age_sec", {}) or {"1m":180, "5m":600, "15m":1800}
    now = int(time.time())

    items: List[Dict[str, Any]] = []
    paths = sorted(glob.glob(os.path.join(KLINES_DIR, "*_*.csv")))
    seen = set()

    for p in paths:
        try:
            sym, tf = parse_name(p)
            if tf not in TF_SEC: 
                continue
            base = sym[:-4] if sym.endswith("USDT") else sym  # affichage sans USDT
            last_ts = last_row_ts(p)
            if last_ts is None:
                st = "grey"; age = None
            else:
                age = max(0, now - int(last_ts))
                lock = Path(f"{LOCKS}/backfill_{sym}_{tf}.lock").exists()
                st = status_for(age, int(fresh.get(tf, 600)), lock)
            key = (base, tf)
            if key in seen: 
                continue
            seen.add(key)
            items.append({
                "sym": base, "tf": tf, "status": st,
                "age_sec": age if age is not None else -1
            })
        except Exception:
            continue

    # On ajoute aussi les couples (sym,tf) “attendus” s’il existe une watchlist.json/yml
    wl_json = Path(f"{BASE}/reports/watchlist.json")
    if wl_json.exists():
        try:
            import json
            data = json.loads(wl_json.read_text())
            for tf, symbols in data.items():
                for s in symbols:
                    base = s[:-4] if s.endswith("USDT") else s
                    if (base, tf) not in seen:
                        items.append({"sym": base, "tf": tf, "status":"grey", "age_sec": -1})
        except Exception:
            pass

    # tri lisible (sym, tf)
    items.sort(key=lambda x: (x["sym"], ["1m","5m","15m"].index(x["tf"]) if x["tf"] in ["1m","5m","15m"] else 9))
    return {"updated_at": now, "items": items}
