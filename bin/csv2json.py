#!/usr/bin/env python3
# Convertit /opt/scalp/var/dashboard/signals.csv -> /opt/scalp/data/{signals.json,history.json}
# Sortie au format {"items":[...]} attendu par /api/*
from __future__ import annotations
import csv, json, os, time

CSV_PATH = "/opt/scalp/var/dashboard/signals.csv"
DATA_DIR = "/opt/scalp/data"
SIG_JSON = os.path.join(DATA_DIR, "signals.json")
HIS_JSON = os.path.join(DATA_DIR, "history.json")
MAX_SIG = 200      # /api/signals
MAX_HIS = 1000     # /api/history

os.makedirs(DATA_DIR, exist_ok=True)

def load_rows(path: str) -> list[dict]:
    if not os.path.exists(path): return []
    with open(path, "r", encoding="utf-8", newline="") as f:
        rdr = csv.DictReader(f)
        rows = [r for r in rdr if r and r.get("ts") and r.get("symbol")]
    return rows

def normalize(r: dict) -> dict:
    # CSV attendu: ts,symbol,tf,signal,details
    ts = int(float(r.get("ts", "0")))
    return {
        "ts": ts,
        "sym": r.get("symbol","").upper(),
        "tf":  r.get("tf",""),
        "side": (r.get("signal","") or "").upper(),   # BUY/SELL/HOLD
        "score": None,
        "entry": r.get("details",""),
    }

def write_json(path: str, items: list[dict]):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"items": items}, f, separators=(",", ":"), ensure_ascii=False)
    os.replace(tmp, path)

def run_once():
    rows = load_rows(CSV_PATH)
    if not rows:
        # garde des JSON valides vides
        write_json(SIG_JSON, [])
        write_json(HIS_JSON, [])
        return
    # normalise du plus récent au plus ancien
    norm = [normalize(r) for r in rows]
    norm.sort(key=lambda x: x["ts"], reverse=True)
    write_json(SIG_JSON, norm[:MAX_SIG])
    write_json(HIS_JSON, norm[:MAX_HIS])

def main():
    # mode boucle léger pour suivre le fichier
    last_mtime = 0.0
    while True:
        try:
            mtime = os.path.getmtime(CSV_PATH) if os.path.exists(CSV_PATH) else 0.0
            if mtime != last_mtime:
                run_once()
                last_mtime = mtime
        except Exception:
            # en cas d'erreur, on essaie de garder des fichiers valides
            try:
                write_json(SIG_JSON, [])
                write_json(HIS_JSON, [])
            except Exception:
                pass
        time.sleep(2)

if __name__ == "__main__":
    main()
