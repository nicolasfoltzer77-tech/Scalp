#!/usr/bin/env python3
from __future__ import annotations
import os, json, time, glob
from collections import defaultdict

BASE = "/opt/scalp/data/klines"                 # fichiers klines *.csv
OUT  = "/opt/scalp/var/dashboard/data_status.json"

# Fraîcheur max autorisée (en secondes) par TF
MAX_AGE = {"1m": 90, "5m": 300, "15m": 900}
MIN_CANDLES = 1500                               # seuil “vert”

def stat_file(path:str):
    try:
        st = os.stat(path)
        return st.st_mtime, st.st_size
    except FileNotFoundError:
        return None, 0

def count_lines(path:str)->int:
    try:
        with open(path,"r",encoding="utf-8") as f:
            # 1ère ligne = header
            return max(0, sum(1 for _ in f)-1)
    except FileNotFoundError:
        return 0

def build():
    now = time.time()
    by_sym_tf = defaultdict(dict)

    for csv in glob.glob(os.path.join(BASE, "*.csv")):
        # ex: BTCUSDT_1m.csv → symbol = BTC, tf = 1m (on retire USDT)
        name = os.path.basename(csv).rsplit(".",1)[0]
        # nom attendu: SYMBOL_TF.csv
        if "_" not in name: 
            continue
        sym_raw, tf = name.rsplit("_",1)
        sym = sym_raw.replace("USDT","")  # affichage sans USDT
        if tf not in MAX_AGE: 
            continue

        mtime,_ = stat_file(csv)
        if not mtime:
            status = "absent"
            candles = 0
        else:
            age = now - mtime
            if age > MAX_AGE[tf]:
                status = "stale"
                candles = 0
            else:
                candles = count_lines(csv)
                status = "fresh" if candles >= MIN_CANDLES else "reloading"

        by_sym_tf[sym][tf] = {"status": status, "candles": candles}

    # Normalise les colonnes TF
    tfs = list(MAX_AGE.keys())
    items = []
    for sym, tfd in sorted(by_sym_tf.items()):
        row = {"symbol": sym, "tfs": {}}
        for tf in tfs:
            row["tfs"][tf] = tfd.get(tf, {"status":"absent","candles":0})
        items.append(row)

    out = {
        "tfs": tfs,
        "min_candles": MIN_CANDLES,
        "items": items,
        "updated_at": int(now)
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT,"w",encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"[ok] écrit {OUT} ({len(items)} symbols)")

if __name__ == "__main__":
    build()
