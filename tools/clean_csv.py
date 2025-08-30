#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
clean_csv.py — nettoie /opt/scalp/var/dashboard/signals.csv :
- supprime les marqueurs de conflit Git (<<<<<<<, =======, >>>>>>>)
- filtre les lignes vides ou manifestement invalides
- force ts en int, symbol/tf/signal en str, details (facultatif)
Écrit le résultat "propre" sur place (overwrite).
"""
import csv, io, os, sys, time

SRC = "/opt/scalp/var/dashboard/signals.csv"
TMP = SRC + ".clean"

MARKERS = ("<<<<<<<", "=======", ">>>>>>>")

def is_bad(line:str)->bool:
    if not line.strip(): return True
    for m in MARKERS:
        if m in line: return True
    return False

def main():
    src = SRC
    if len(sys.argv) > 1: src = sys.argv[1]
    if not os.path.exists(src):
        print(f"[clean_csv] WARNING: missing file: {src}")
        return 0

    with open(src, "r", encoding="utf-8", newline="") as f:
        raw = f.read().splitlines()

    # drop conflict markers & blanks
    raw = [ln for ln in raw if not is_bad(ln)]

    # quick sniff: if there is a header, keep it; otherwise, we'll write a header
    has_header = False
    if raw:
        head = raw[0].lower()
        has_header = all(k in head for k in ("ts", "symbol", "tf", "signal"))

    # csv normalize -> write tmp
    out = io.StringIO()
    w = csv.writer(out)
    if not has_header:
        w.writerow(["ts", "symbol", "tf", "signal", "details"])

    for ln in raw[1:] if has_header else raw:
        try:
            parts = next(csv.reader([ln]))
        except Exception:
            # fallback split by comma (grossier mais robuste)
            parts = [p.strip() for p in ln.split(",")]

        if len(parts) < 4:  # ts,symbol,tf,signal[,details]
            continue

        ts, symbol, tf, signal = parts[:4]
        details = parts[4] if len(parts) >= 5 else ""

        # validations minimales
        try:
            ts_int = int(str(ts).strip())
        except Exception:
            continue
        symbol = str(symbol).strip().upper()
        tf = str(tf).strip()
        signal = str(signal).strip().upper()
        details = str(details).strip()

        if not symbol.endswith("USDT"):  # on n'accepte que XXXUSDT
            continue
        if tf not in ("1m","5m","15m","30m","1h","4h","1d"):
            # tolère 1m/5m/15m usuels ; on ignore le reste
            continue
        if signal not in ("BUY","SELL","HOLD"):
            signal = "HOLD"

        w.writerow([ts_int, symbol, tf, signal, details])

    data = out.getvalue()
    with open(TMP, "w", encoding="utf-8", newline="") as f:
        f.write(data)

    # replace atomiquement
    os.replace(TMP, src)
    print(f"[clean_csv] OK -> {src} ({len(data.splitlines())-1} rows)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
