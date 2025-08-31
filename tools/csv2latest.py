#!/usr/bin/env python3
import csv, json, time
SRC = "/opt/scalp/var/dashboard/signals.csv"
DST = "/opt/scalp/docs/latest.json"

best = {}  # (symbol, tf) -> {ts, symbol, tf, signal, details}
with open(SRC, newline="") as f:
    rdr = csv.reader(f)
    rows = list(rdr)
    # détecte un éventuel header
    if rows and rows[0] and rows[0][0].lower() in ("ts","timestamp"):
        rows = rows[1:]
    for r in rows:
        if len(r) < 4: 
            continue
        ts, symbol, tf, signal = r[:4]
        details = r[4] if len(r) > 4 else ""
        try:
            ts_i = int(ts)
        except:
            continue
        k = (symbol.strip(), tf.strip())
        cur = best.get(k)
        if (cur is None) or (ts_i > cur["ts"]):
            best[k] = {"ts": ts_i, "symbol": k[0], "tf": k[1], "signal": signal.strip(), "details": details.strip()}

out = sorted(best.values(), key=lambda x: (x["symbol"], {"1m":0,"3m":1,"5m":2,"15m":3,"30m":4,"1h":5}.get(x["tf"], 99)))
with open(DST, "w") as g:
    json.dump(out, g, separators=(",",":"))
print(f"wrote {len(out)} records -> {DST}")
