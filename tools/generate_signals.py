#!/usr/bin/env python3
import csv, json, os, time, sys

CSV_PATH = os.environ.get("SCALP_SIGNALS_CSV","/opt/scalp/var/dashboard/signals.csv")
rows = []

# Schéma CSV attendu: ts,symbol,tf,signal,details
# Exemple:
# 1756635000,BTC,1m,HOLD,
# 1756635000,ETH,5m,BUY,sma_cross_fast=BUY;rsi=NEUTRAL

if os.path.isfile(CSV_PATH):
    with open(CSV_PATH, newline="") as f:
        r = csv.DictReader(f, fieldnames=["ts","symbol","tf","signal","details"])
        for rec in r:
            # nettoyage min
            try:
                ts = int(rec["ts"])
            except Exception:
                ts = int(time.time())
            rows.append({
                "ts": ts,
                "symbol": rec["symbol"].strip(),
                "tf": rec["tf"].strip(),
                "signal": rec["signal"].strip().upper() or "HOLD",
                "details": rec.get("details","").strip()
            })

# Si rien en entrée -> un fallback lisible
if not rows:
    rows = [
        {"ts": int(time.time()), "symbol":"BTC", "tf":"1m",  "signal":"HOLD", "details":""},
        {"ts": int(time.time()), "symbol":"BTC", "tf":"5m",  "signal":"HOLD", "details":""},
        {"ts": int(time.time()), "symbol":"BTC", "tf":"15m", "signal":"HOLD", "details":""},
    ]

json.dump(rows, sys.stdout, separators=(",",":"))
