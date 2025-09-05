#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, csv, sys
from collections import defaultdict

CSV_PATH = os.environ.get("SCALP_SIGNALS_CSV", "/opt/scalp/var/dashboard/signals.csv")

def parse_details(s: str):
    out={}
    for p in (s or "").split(";"):
        p=p.strip()
        if "=" in p:
            k,v=p.split("=",1)
            out[k.strip()] = v.strip().upper()
    return out

def main(filter_syms=None, filter_tfs=None):
    if not os.path.exists(CSV_PATH):
        print(f"[ERR] CSV introuvable: {CSV_PATH}", file=sys.stderr); sys.exit(2)
    last = {}  # (sym,tf) -> (ts, side, details_dict)
    with open(CSV_PATH, newline='', encoding='utf-8', errors='ignore') as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            sym = (r.get("symbol") or "").upper()
            tf  = (r.get("tf") or "")
            if filter_syms and sym not in filter_syms: continue
            if filter_tfs and tf not in filter_tfs: continue
            try:
                ts = int(float(r.get("ts") or 0))
            except: ts = 0
            side = (r.get("signal") or "").upper() or "HOLD"
            det = parse_details(r.get("details") or "")
            key = (sym, tf)
            if key not in last or ts > last[key][0]:
                last[key] = (ts, side, det)

    if not last:
        print("Aucun couple (sym,tf) dans le filtre.")
        return
    # tri par sym, tf
    for (sym, tf) in sorted(last.keys()):
        ts, side, det = last[(sym,tf)]
        print(f"\n[{sym} @ {tf}]  ts={ts}  side={side}")
        if not det:
            print("  (aucun détail parsé)")
        else:
            # liste les composants qui bloquent (HOLD) vs OK
            holds = [k for k,v in det.items() if v=="HOLD"]
            oks   = [k for k,v in det.items() if v in ("BUY","SELL","LONG","SHORT")]
            if holds:
                print("  HOLD by:", ", ".join(sorted(holds)))
            if oks:
                print("  OK   by:", ", ".join(sorted(oks)))
            # tout brut :
            print("  details:", det)

if __name__ == "__main__":
    syms = None
    tfs = None
    # usage : why_hold.py "BTCUSDT,ETHUSDT" "1m,5m"
    if len(sys.argv) >= 2 and sys.argv[1].strip():
        syms = set(s.strip().upper() for s in sys.argv[1].split(",") if s.strip())
    if len(sys.argv) >= 3 and sys.argv[2].strip():
        tfs = set(s.strip() for s in sys.argv[2].split(",") if s.strip())
    main(syms, tfs)
