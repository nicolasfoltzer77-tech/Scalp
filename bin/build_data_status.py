#!/usr/bin/env python3
from __future__ import annotations
import os, re, json, time
from pathlib import Path

DATA = Path("/opt/scalp/data")
OUT  = Path("/opt/scalp/var/dashboard/data_status.json")

# seuils de fraicheur (âge max en secondes)
THRESH = {"1m": 120, "5m": 8*60, "15m": 25*60}
# au-delà de ce seuil on passe "stale"
STALE  = {"1m": 10*60, "5m": 60*60, "15m": 3*60*60}

rx = re.compile(r"^(?P<sym>.+)_(?P<tf>1m|5m|15m)\.jsonl$", re.I)

def tail_last_ts_and_count(p: Path):
    if not p.exists(): return None, 0
    # lit en arrière: on ne parcourt pas tout le fichier
    try:
        with p.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            back = min(size, 128*1024)
            f.seek(size - back)
            lines = f.read().decode("utf-8", "ignore").strip().splitlines()
        # dernier JSON valide
        import json as _json
        for line in reversed(lines):
            line=line.strip()
            if not line: continue
            try:
                o = _json.loads(line)
                ts = float(o.get("ts", 0))
                break
            except Exception:
                continue
        else:
            ts = 0.0
        # compte approximatif des bougies (nb total de lignes)
        cnt = sum(1 for _ in open(p, "r", encoding="utf-8", errors="ignore"))
        return ts, cnt
    except Exception:
        return None, 0

now = time.time()
symbols = {}
for f in DATA.glob("*.jsonl"):
    m = rx.match(f.name)
    if not m: continue
    sym = m.group("sym").upper()
    tf  = m.group("tf")
    ts, cnt = tail_last_ts_and_count(f)
    if ts is None: status = "absent"
    else:
        age = now - (ts/1000 if ts>10_000_000_000 else ts)
        if age < THRESH[tf]:        status = "fresh"
        elif age < STALE[tf]:       status = "reloading"
        else:                       status = "stale"
    symbols.setdefault(sym, {"symbol": sym, "tfs": {}})
    symbols[sym]["tfs"][tf] = {"status": status, "candles": cnt}

items = list(symbols.values())
payload = {"items": items, "updated_at": int(now)}

OUT.parent.mkdir(parents=True, exist_ok=True)
tmp = OUT.with_suffix(".json.tmp")
with tmp.open("w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, separators=(",",":"))
os.replace(tmp, OUT)
print(f"wrote {OUT} with {len(items)} symbols")
