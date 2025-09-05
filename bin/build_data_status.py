#!/usr/bin/env python3
from __future__ import annotations
import os, json, time, glob, re
from collections import defaultdict

BASE = "/opt/scalp/data/klines"
OUT  = "/opt/scalp/var/dashboard/data_status.json"

# Fraîcheur max (s) par TF
MAX_AGE      = {"1m": 90, "5m": 300, "15m": 900}
MIN_CANDLES  = 1500

HDR_RE = re.compile(r'[A-Za-z]')  # détecte une entête (caractères alpha)

def count_lines(path:str)->int:
    """Compte les lignes données (ignore blank + éventuel header)."""
    n = 0
    header_checked = False
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                if not header_checked:
                    header_checked = True
                    # si la 1re ligne contient des lettres, on la considère comme header
                    if HDR_RE.search(s):
                        continue
                n += 1
    except FileNotFoundError:
        return 0
    return n

def build():
    now = time.time()
    tfs = list(MAX_AGE.keys())
    by_sym_tf = defaultdict(dict)

    for csv in glob.glob(os.path.join(BASE, "*.csv")):
        name = os.path.basename(csv).rsplit(".",1)[0]  # BTCUSDT_1m
        if "_" not in name: 
            continue
        sym_raw, tf = name.rsplit("_",1)
        if tf not in MAX_AGE:
            continue
        sym = sym_raw.replace("USDT","")

        try:
            st = os.stat(csv)
            age = now - st.st_mtime
        except FileNotFoundError:
            by_sym_tf[sym][tf] = {"status":"absent","candles":0}
            continue

        if age > MAX_AGE[tf]:
            status = "stale"
            candles = 0
        else:
            candles = count_lines(csv)
            status  = "fresh" if candles >= MIN_CANDLES else "reloading"

        by_sym_tf[sym][tf] = {"status":status, "candles":candles}

    items = []
    for sym, tfd in sorted(by_sym_tf.items()):
        row = {"symbol": sym, "tfs": {}}
        for tf in tfs:
            row["tfs"][tf] = tfd.get(tf, {"status":"absent","candles":0})
        items.append(row)

    out = {"tfs": tfs, "min_candles": MIN_CANDLES, "items": items, "updated_at": int(now)}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"[ok] {OUT} -> {len(items)} symbols")

if __name__ == "__main__":
    build()
