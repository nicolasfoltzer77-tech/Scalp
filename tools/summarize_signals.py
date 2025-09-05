#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, csv, sys, re, json
from collections import Counter, defaultdict
CSV_PATH = os.environ.get("SCALP_SIGNALS_CSV", "/opt/scalp/var/dashboard/signals.csv")

def parse_details(s: str):
    parts = [p.strip() for p in (s or "").split(";") if p.strip()]
    out = {}
    for p in parts:
        if "=" in p:
            k,v = p.split("=",1)
            out[k.strip()] = v.strip().upper()
    return out

def main(limit=None):
    if not os.path.exists(CSV_PATH):
        print(f"[ERR] CSV introuvable: {CSV_PATH}", file=sys.stderr); sys.exit(2)
    tot = 0
    by_side = Counter()
    by_sym = defaultdict(Counter)
    by_tf  = defaultdict(Counter)
    by_comp = defaultdict(Counter)   # composant -> {BUY/HOLD/SELL: n}
    combos  = Counter()               # (sym,tf,side)
    last_by_key = {}                 # (sym,tf) -> dernier détail

    with open(CSV_PATH, newline='', encoding='utf-8', errors='ignore') as f:
        rdr = csv.DictReader(f)
        rows = list(rdr)
        if limit:
            rows = rows[-limit:]
        for r in rows:
            tot += 1
            sym = (r.get("symbol") or "").upper()
            tf  = (r.get("tf") or "")
            side = (r.get("signal") or "").upper() or "HOLD"
            det = r.get("details") or ""
            d = parse_details(det)

            by_side[side] += 1
            by_sym[sym][side] += 1
            by_tf[tf][side] += 1
            combos[(sym,tf,side)] += 1
            last_by_key[(sym,tf)] = d  # fin = plus récent

            for k,v in d.items():
                by_comp[k][v] += 1

    print("=== GLOBAL ===")
    print(f"total rows: {tot}")
    print("sides:", dict(by_side))
    print()

    # Top sym et tf
    def top3(counter_map):
        return sorted(((k, dict(v)) for k,v in counter_map.items()),
                      key=lambda kv: sum(kv[1].values()), reverse=True)[:12]

    print("=== PAR SYM (top) ===")
    for k,v in top3(by_sym):
        print(f"{k:>10}: {v}")
    print()

    print("=== PAR TF ===")
    for k,v in sorted(((k, dict(v)) for k,v in by_tf.items())):
        print(f"{k:>4}: {v}")
    print()

    print("=== PAR COMPOSANT (qui bloque ?) ===")
    for comp, cnt in by_comp.items():
        tot_c = sum(cnt.values())
        pct = {k: round(100*cnt[k]/tot_c,1) for k in cnt}
        print(f"{comp:>18}: {dict(cnt)}  pct={pct}")
    print()

    # Derniers états par (sym,tf) pour inspection
    print("=== DERS. ETATS PAR (sym,tf) — PREVIEW 10 ===")
    i=0
    for k,v in last_by_key.items():
        print(k, v)
        i+=1
        if i>=10: break

if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv)>1 else None
    main(lim)
