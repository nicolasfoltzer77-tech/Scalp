#!/usr/bin/env python3
from __future__ import annotations
import os, re, time, json, io
from pathlib import Path
from typing import Dict, Tuple, List

IN_DIR  = Path(os.getenv("KLINES_IN",  "/opt/data/klines"))
OUT_DIR = Path(os.getenv("KLINES_OUT", "/opt/scalp/data"))
OUT_DIR.mkdir(parents=True, exist_ok=True)

PAT = re.compile(r"^([A-Z0-9]+)_(1m|5m|15m)\.csv$")
MAX_ROWS_PER_FILE = 5000

def parse_filename(p: Path) -> Tuple[str,str] | None:
    m = PAT.match(p.name)
    return (m.group(1), m.group(2)) if m else None

def load_csv(p: Path) -> List[List[float]]:
    raw = p.read_text(encoding="utf-8", errors="ignore").strip()
    if not raw:
        return []
    first = raw.splitlines()[0].lower()
    has_header = ("timestamp" in first) or (",o," in first) or (",open," in first)
    rows = []
    for line in (raw.splitlines()[1:] if has_header else raw.splitlines()):
        if not line.strip():
            continue
        parts = [s.strip() for s in line.split(",")]
        if len(parts) < 6: 
            continue
        try:
            ts = float(parts[0]); o=float(parts[1]); h=float(parts[2])
            l=float(parts[3]); c=float(parts[4]); v=float(parts[5])
            rows.append([ts,o,h,l,c,v])
        except: 
            continue
    return rows

def to_ndjson(sym: str, tf: str, rows: List[List[float]]) -> str:
    out = io.StringIO()
    for ts,o,h,l,c,v in rows[-MAX_ROWS_PER_FILE:]:
        obj = {"ts": int(ts), "symbol": sym, "tf": tf,
               "o": o, "h": h, "l": l, "c": c, "v": v}
        json.dump(obj, out, separators=(",",":"))
        out.write("\n")
    return out.getvalue()

def convert_file(csv_path: Path):
    parsed = parse_filename(csv_path)
    if not parsed:
        return
    sym, tf = parsed
    rows = load_csv(csv_path)
    nd = to_ndjson(sym, tf, rows)
    out_path = OUT_DIR / f"{sym}_{tf}.jsonl"
    tmp = out_path.with_suffix(".tmp")
    tmp.write_text(nd, encoding="utf-8")
    os.replace(tmp, out_path)
    print(f"[klines2jsonl] wrote {out_path.name} rows={len(rows)}")

def scan_once():
    for p in IN_DIR.glob("*.csv"):
        try:
            convert_file(p)
        except Exception as e:
            print(f"[klines2jsonl] ERROR on {p.name}: {e}")

def main():
    print(f"[klines2jsonl] start  IN={IN_DIR}  OUT={OUT_DIR}")
    scan_once()
    mtimes: Dict[str,float] = {p.name:p.stat().st_mtime for p in IN_DIR.glob("*.csv")}
    while True:
        time.sleep(5)
        for p in IN_DIR.glob("*.csv"):
            m = p.stat().st_mtime
            if mtimes.get(p.name) != m:
                convert_file(p)
                mtimes[p.name] = m

if __name__ == "__main__":
    main()
