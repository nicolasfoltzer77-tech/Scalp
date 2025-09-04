#!/usr/bin/env python3
from __future__ import annotations
import csv, json, os, time
from datetime import datetime, timezone
from collections import deque, defaultdict

CSV_PATH   = "/opt/scalp/var/dashboard/signals.csv"
DATA_DIR   = "/opt/scalp/data"
SNAP_JSON  = f"{DATA_DIR}/signals.json"
HIST_JSON  = f"{DATA_DIR}/history.json"
HEAT_JSON  = f"{DATA_DIR}/heatmap.json"

MAX_SNAPSHOT = 200
MAX_HISTORY  = 2000
TF_ORDER     = ["1m","5m","15m","1h"]

os.makedirs(DATA_DIR, exist_ok=True)

def now_iso(): return datetime.now(timezone.utc).isoformat()

def side_value(side:str) -> float:
    s = (side or "").upper()
    if s.startswith("BUY"):  return 1.0
    if s.startswith("SELL"): return 0.0
    return 0.5

def load_csv_rows():
    if not os.path.exists(CSV_PATH): return []
    rows = []
    with open(CSV_PATH, newline="") as f:
        r = csv.reader(f)
        for line in r:
            if not line: continue
            try:
                epoch = int(line[0]); sym=line[1]; tf=line[2]; side=line[3]
                strat = line[4] if len(line)>4 else ""
            except Exception:
                continue
            ts = datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
            rows.append({"ts":ts,"sym":sym,"tf":tf,"side":side.upper(),
                         "score":None,"entry":None,"strategies":strat})
    return rows

def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w") as f: json.dump(obj, f, separators=(",",":"))
    os.replace(tmp, path)

def baseline():
    now = now_iso()
    write_json(SNAP_JSON, {"as_of": now, "items": []})
    write_json(HIST_JSON, {"as_of": now, "items": []})
    write_json(HEAT_JSON, {"as_of": now, "cells": []})

def build_heatmap(rows):
    last = {}
    for r in rows:
        key = (r["sym"], r["tf"])
        if key not in last or r["ts"] > last[key]["ts"]:
            last[key] = r
    by_sym = defaultdict(list)
    for (sym, tf), r in last.items(): by_sym[sym].append(side_value(r["side"]))
    sym_ranked = sorted(by_sym.keys(),
                        key=lambda s: (sum(by_sym[s])/max(1,len(by_sym[s]))),
                        reverse=True)
    cells=[]
    for x, sym in enumerate(sym_ranked[:20]):
        for y, tf in enumerate(TF_ORDER):
            if (sym, tf) in last:
                cells.append({"x":x,"y":y,"v":side_value(last[(sym,tf)]["side"])})
    return {"as_of": now_iso(), "cells": cells}

def main_loop():
    # baseline au démarrage quoi qu’il arrive
    try: baseline()
    except Exception: pass

    hist = deque(maxlen=MAX_HISTORY)
    try:
        if os.path.exists(HIST_JSON):
            with open(HIST_JSON) as f:
                for it in (json.load(f).get("items") or []): hist.append(it)
    except Exception: pass

    last_mtime = -1
    while True:
        try:
            mtime = os.path.getmtime(CSV_PATH) if os.path.exists(CSV_PATH) else -1
            if mtime != last_mtime:
                last_mtime = mtime
                rows = load_csv_rows()
                if rows is None: rows = []
                # snapshot
                write_json(SNAP_JSON, {"as_of": now_iso(), "items": rows[-MAX_SNAPSHOT:]})
                # history (tail borné)
                for r in rows[-MAX_HISTORY:]: hist.append(r)
                write_json(HIST_JSON, {"as_of": now_iso(), "items": list(hist)})
                # heatmap
                write_json(HEAT_JSON, build_heatmap(rows) if rows else {"as_of": now_iso(),"cells":[]})
        except Exception:
            # on remet un baseline valide en cas d’erreur
            try: baseline()
            except Exception: pass
        time.sleep(2)

if __name__ == "__main__":
    main_loop()
