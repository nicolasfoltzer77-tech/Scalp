#!/usr/bin/env python3
import csv, json, sys, time
from pathlib import Path

src = Path("/opt/scalp/var/dashboard/signals.csv")
dst = Path("/opt/scalp/docs/signals.json")

rows = []
with src.open(newline='', encoding='utf-8') as f:
    r = csv.reader(f)
    for line in r:
        if not line or len(line) < 4:  # ts, symbol, tf, signal[, details]
            continue
        ts_raw, sym, tf, sig = line[:4]
        details = line[4] if len(line) > 4 else ""
        try:
            ts = int(float(ts_raw))  # accepte ts ou ts.ms
        except Exception:
            # skip lignes pourries (ex: marqueurs merge)
            continue
        rows.append({
            "ts": ts,
            "symbol": sym.strip(),
            "tf": tf.strip(),
            "signal": sig.strip().upper(),
            "details": details.strip()
        })

# tri chrono puis on peut limiter si besoin (ex: garder 20000 dernières)
rows.sort(key=lambda x: x["ts"])
# rows = rows[-20000:]

with dst.open("w", encoding="utf-8") as out:
    json.dump(rows, out, separators=(',', ':'), ensure_ascii=False)
