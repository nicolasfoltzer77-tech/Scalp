#!/usr/bin/env python3
from __future__ import annotations
import os, json, time
from pathlib import Path
from typing import List, Tuple

ROOT = Path("/opt/scalp/data")     # racine à scanner
OUT  = Path("/opt/scalp/data/last10-data.json")  # fichier lu par l’UI
MAX  = 10

def collect() -> List[Tuple[float, Path]]:
    exts = (".json",".jsonl")
    files: List[Tuple[float,Path]] = []
    # profondeur 2: /data/* et /data/*/*  (couvre symbol/tf/ohlcv.jsonl)
    for p in list(ROOT.glob("*")) + list(ROOT.glob("*/*")):
        try:
            if p.is_file() and p.suffix in exts:
                files.append((p.stat().st_mtime, p))
        except FileNotFoundError:
            pass
    files.sort(key=lambda x: x[0], reverse=True)
    return files[:MAX]

def main():
    items=[]
    for mtime, path in collect():
        try:
            items.append({
                "name": path.name,
                "path": str(path),
                "size": path.stat().st_size,
                "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(mtime))
            })
        except FileNotFoundError:
            continue
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, separators=(",",":")), encoding="utf-8")
    os.replace(tmp, OUT)

if __name__ == "__main__":
    main()
