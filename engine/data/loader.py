# /opt/scalp/engine/data/loader.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import json, pathlib
from typing import List, Optional, Any

DATA_ROOT = pathlib.Path("/opt/scalp/data")

def _load_json_or_jsonl(p: pathlib.Path) -> Optional[List[Any]]:
    if not p.exists(): return None
    if p.suffix == ".jsonl":
        arr = []
        with p.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    try: arr.append(json.loads(line))
                    except Exception: pass
        return arr or None
    else:
        try:
            return json.loads(p.read_text())
        except Exception:
            return None

def load_latest_ohlcv(symbol: str, tf: str, lookback: int = 200) -> Optional[list]:
    base = DATA_ROOT / symbol / tf
    for name in ("ohlcv.jsonl", "ohlcv.json", "OHLCV.jsonl", "OHLCV.json"):
        data = _load_json_or_jsonl(base / name)
        if data:
            # standard attendu: [ts, o, h, l, c, v]
            return data[-lookback:]
    return None
