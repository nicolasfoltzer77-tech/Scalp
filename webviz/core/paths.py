# -*- coding: utf-8 -*-
import os, json, io, csv
from typing import Iterable, Optional, Dict, List

def _first_existing(paths: Iterable[str]) -> Optional[str]:
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None

def resolve_paths() -> Dict[str, Optional[str]]:
    data_dir = "/opt/scalp/data"
    var_dash = "/opt/scalp/var/dashboard"
    return {
        "signals_csv": _first_existing([
            os.environ.get("SCALP_SIGNALS_CSV"),
            f"{var_dash}/signals.csv",
        ]),
        "signals_json": _first_existing([f"{data_dir}/signals.json"]),
        "history_json": _first_existing([f"{data_dir}/history.json"]),
        "heatmap_json": _first_existing([f"{data_dir}/heatmap.json"]),
    }

def load_json(path: Optional[str]):
    if not path: return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def tail_lines(path: str, max_lines: int = 5000) -> List[str]:
    if not path or not os.path.exists(path): return []
    with open(path, "rb") as f:
        data = f.read()[-(1024*1024*4):]  # 4 Mo max
    text = data.decode("utf-8", errors="ignore")
    lines = text.strip().splitlines()
    return lines[-max_lines:]

def parse_signals_csv_lines(lines: List[str]) -> List[Dict]:
    if not lines: return []
    if not lines[0].lower().startswith("ts,"):
        lines = ["ts,symbol,tf,signal,details"] + lines
    rdr = csv.DictReader(io.StringIO("\n".join(lines)))
    out = []
    for r in rdr:
        if not r: continue
        try:
            ts = int(float(r.get("ts") or 0))
        except Exception:
            ts = 0
        sym = (r.get("symbol") or r.get("sym") or "").strip()
        tf = (r.get("tf") or "").strip()
        side = (r.get("signal") or r.get("side") or "HOLD").strip().upper()
        det = (r.get("details") or r.get("entry") or "").strip()
        if not sym: continue
        out.append({
            "ts": ts, "sym": sym, "tf": tf, "side": side,
            "score": 0 if side=="HOLD" else (1 if side=="BUY" else -1),
            "entry": det, "details": det
        })
    out.sort(key=lambda x: x["ts"], reverse=True)
    return out

def load_signals_any(limit_scan: int = 5000) -> List[Dict]:
    p = resolve_paths()
    if p["signals_csv"]:
        return parse_signals_csv_lines(tail_lines(p["signals_csv"], limit_scan))
    js = load_json(p["signals_json"])
    items = []
    if isinstance(js, dict) and "items" in js: items = js["items"]
    elif isinstance(js, list): items = js
    norm=[]
    for r in items:
        side = (r.get("side") or r.get("signal") or "HOLD").upper()
        norm.append({
            "ts": int(r.get("ts",0)),
            "sym": r.get("sym") or r.get("symbol") or "",
            "tf": r.get("tf") or "",
            "side": side,
            "score": 0 if side=="HOLD" else (1 if side=="BUY" else -1),
            "entry": r.get("entry") or r.get("details") or "",
            "details": r.get("details") or r.get("entry") or "",
        })
    norm.sort(key=lambda x: x["ts"], reverse=True)
    return norm
