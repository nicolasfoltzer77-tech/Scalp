#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Résumé du fichier signals.csv
- Compte global BUY/SELL/HOLD
- Par symbole
- Par timeframe
- Vérifie les composantes dans la colonne details (sma_cross_fast, rsi_reversion, ema_trend)

Usage:
  summarize_signals.py [LIMIT]
"""

import csv, os, sys, collections

CSV_PATH = os.environ.get("SCALP_SIGNALS_CSV", "/opt/scalp/var/dashboard/signals.csv")

limit = int(sys.argv[1]) if len(sys.argv) > 1 else 5000

def read_signals(path, limit):
    rows = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows[-limit:]

rows = read_signals(CSV_PATH, limit)

global_count = collections.Counter()
by_sym = collections.Counter()
by_tf = collections.Counter()
by_comp = collections.Counter()

preview = []

for r in rows:
    sym = r.get("sym") or r.get("symbol")
    tf = r.get("tf") or r.get("timeframe")
    side = r.get("side") or r.get("signal")
    details = r.get("details") or r.get("entry") or ""

    global_count[side] += 1
    by_sym[sym] += 1
    by_tf[tf] += 1

    for part in details.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            if v.strip().upper() == "HOLD":
                by_comp[k] += 1

    preview.append(((sym, tf), {"side": side, "details": details}))

print("=== GLOBAL ===")
print(f"total rows: {len(rows)}")
print("sides:", dict(global_count))

print("\n=== PAR SYM (top) ===")
print(dict(by_sym.most_common(5)))

print("\n=== PAR TF ===")
print(dict(by_tf.most_common()))

print("\n=== PAR COMPOSANT (qui bloque ?) ===")
print(dict(by_comp.most_common()))

print("\n=== DERS. ETATS PAR (sym,tf) — PREVIEW 10 ===")
for (sym, tf), data in preview[-10:]:
    print((sym, tf), data)
