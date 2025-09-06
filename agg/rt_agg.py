#!/usr/bin/env python3
from __future__ import annotations
import json, os, time
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

BASE = Path("/opt/scalp")
OUT  = BASE / "data"
OUT.mkdir(parents=True, exist_ok=True)

API_BASE      = os.getenv("API_BASE", "http://127.0.0.1")
API_WATCHLIST = f"{API_BASE}/api/watchlist"
API_SIGNALS   = f"{API_BASE}/api/signals"
API_POSITIONS = f"{API_BASE}/api/positions"

# Fallback fichiers
F_WATCHLIST = BASE / "var" / "dashboard" / "data_status.json"
F_SIGNALS   = OUT / "signals.json"
F_POSITIONS = BASE / "reports" / "positions.json"

def now_iso(): return datetime.now(timezone.utc).isoformat()

def _log(msg): print(f"[{now_iso()}] {msg}", flush=True)

def http_get_json(url: str, timeout=4):
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=timeout) as r:
        data = r.read()
    try:
        return json.loads(data.decode("utf-8"))
    except Exception:
        items = []
        for line in data.splitlines():
            line=line.strip()
            if not line: 
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                pass
        return items

def file_get_json(path: Path):
    if not path.exists(): 
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

# ---------- utilitaires de normalisation ----------
ALIASES = {
    "sym":   ["sym","symbol","ticker","pair","asset"],
    "side":  ["side","signal","action","direction","status"],
    "score": ["score","strength","prob","probability","confidence","value"],
    "entry": ["entry","entry_price","price","px","last_price","fill_price"],
    "ts":    ["ts","timestamp","time","datetime","date"],
    "qty":   ["qty","quantity","size","amount"],
    "sl":    ["sl","stop","stop_loss"],
    "tp":    ["tp","take_profit","target"],
}
def pick(d: dict, keys: list[str]):
    for k in keys:
        if k in d: return d[k]
    return None
def to_upper(s): 
    return s.upper() if isinstance(s,str) else s
def to_iso(ts):
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z","+00:00")).astimezone(timezone.utc).isoformat()
        except Exception:
            return now_iso()
    try:
        x = float(ts)
        if x > 10_000_000_000: x/=1000.0
        return datetime.fromtimestamp(x, tz=timezone.utc).isoformat()
    except Exception:
        return now_iso()
def to_float(x):
    try:
        if isinstance(x,str) and x.endswith("%"): return float(x[:-1])/100.0
        v = float(x)
        if v>1.0: v/=100.0
        return max(0.0,min(1.0,v))
    except Exception: return None

# ---------- Signals ----------
def normalize_signal(raw: dict):
    sym   = pick(raw, ALIASES["sym"])
    if not sym: return None
    side  = pick(raw, ALIASES["side"])
    score = pick(raw, ALIASES["score"])
    entry = pick(raw, ALIASES["entry"])
    ts    = pick(raw, ALIASES["ts"])

    side_u = to_upper(side) or "HOLD"
    if side_u in ("LONG","BUY","BULL","UP"):          side_u = "BUY"
    elif side_u in ("SHORT","SELL","BEAR","DOWN"):    side_u = "SELL"
    elif side_u not in ("BUY","SELL"):                side_u = "HOLD"

    return {
        "ts":   to_iso(ts),
        "sym":  to_upper(sym),
        "side": side_u,
        "score": to_float(score),
        "entry": to_float(entry),
    }

def signals_from_api_or_file():
    # API d'abord
    try:
        data = http_get_json(API_SIGNALS)
        src  = f"API {API_SIGNALS}"
    except Exception as e:
        _log(f"signals: API KO ({e}), fallback fichier {F_SIGNALS}")
        try:
            data = file_get_json(F_SIGNALS)
            src  = f"FILE {F_SIGNALS}"
        except Exception as e2:
            _log(f"signals: FILE KO ({e2})")
            return [], "none"

    rows=[]
    if isinstance(data, dict):
        rows = data.get("items") or data.get("signals") or []
        if isinstance(rows, dict): rows = [rows]
        if not isinstance(rows, list): rows=[]
    elif isinstance(data, list):
        rows = data

    out=[]
    for r in rows:
        if not isinstance(r, dict): 
            continue
        n = normalize_signal(r)
        if not n: 
            continue
        if n["side"] in ("BUY","SELL"):
            out.append(n)
    return out[:500], src

# ---------- Heatmap ----------
def extract_watchlist_items(obj):
    items=[]
    def add(sym, score):
        s = to_float(score)
        if sym and s is not None:
            items.append({"sym": to_upper(sym), "score": s})
    if obj is None: return items
    if isinstance(obj, dict):
        if "items" in obj and isinstance(obj["items"], list):
            for it in obj["items"]:
                if isinstance(it,dict):
                    add(pick(it,ALIASES["sym"]), pick(it,ALIASES["score"]))
        else:
            for k,v in obj.items():
                if isinstance(v,(int,float,str)):
                    add(k,v)
    elif isinstance(obj,list):
        for it in obj:
            if isinstance(it,dict):
                add(pick(it,ALIASES["sym"]), pick(it,ALIASES["score"]))
    return items

def heatmap_from_api_or_file():
    # 1) API
    try:
        data = http_get_json(API_WATCHLIST)
        items = extract_watchlist_items(data)
        src = f"API {API_WATCHLIST}"
    except Exception as e:
        _log(f"watchlist: API KO ({e}), fallback fichier {F_WATCHLIST}")
        # 2) Fichier data_status.json -> score par statut
        try:
            ds  = file_get_json(F_WATCHLIST)
            score_map = {"fresh":1.0, "reloading":0.6, "stale":0.3, "absent":0.0}
            items=[]
            for it in ds.get("items", []):
                sym = to_upper(it.get("symbol") or it.get("sym"))
                tfs = it.get("tfs", {})
                # moyenne simple des 3 TF si présentes
                vals=[]
                for tf in ("1m","5m","15m"):
                    st = (tfs.get(tf) or {}).get("status")
                    if st in score_map: vals.append(score_map[st])
                if sym and vals:
                    items.append({"sym": sym, "score": sum(vals)/len(vals)})
            src = f"FILE {F_WATCHLIST}"
        except Exception as e2:
            _log(f"watchlist: FILE KO ({e2})")
            items=[]
            src="none"

    cols=4
    cells=[]
    for i,it in enumerate(sorted(items, key=lambda x:x.get("score",0), reverse=True)):
        cells.append({"x": i%cols, "y": i//cols, "v": float(it["score"]), "sym": it["sym"]})
    return {"as_of": now_iso(), "cells": cells}, src

# ---------- History ----------
def history_from_api_or_file():
    # API
    try:
        data = http_get_json(API_POSITIONS)
        src  = f"API {API_POSITIONS}"
    except Exception as e:
        # fichier optionnel
        try:
            data = file_get_json(F_POSITIONS)
            src  = f"FILE {F_POSITIONS}"
        except Exception:
            return [], "none"
    rows=[]
    if isinstance(data, dict):
        rows = data.get("items") or data.get("positions") or []
    elif isinstance(data, list):
        rows = data
    out=[]
    for r in rows:
        if not isinstance(r,dict): 
            continue
        out.append({
            "ts":   to_iso(pick(r,ALIASES["ts"])),
            "sym":  to_upper(pick(r,ALIASES["sym"])) or "",
            "side": to_upper(pick(r,ALIASES["side"])) or "",
            "qty":  pick(r, ALIASES["qty"]),
            "sl":   pick(r, ALIASES["sl"]),
            "tp":   pick(r, ALIASES["tp"]),
            "entry": pick(r, ALIASES["entry"]),
        })
    return out[:200], src

def write_json_atomic(path: Path, payload):
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",",":"))
    os.replace(tmp, path)

def main():
    _log(f"rt_agg start; API_BASE={API_BASE}  OUT={OUT}")
    while True:
        try:
            signals,  s_src = signals_from_api_or_file()
            heatmap,  h_src = heatmap_from_api_or_file()
            history,  p_src = history_from_api_or_file()

            write_json_atomic(OUT / "signals.json",  signals)
            write_json_atomic(OUT / "heatmap.json",  heatmap)
            write_json_atomic(OUT / "history.json",  history)

            _log(f"wrote signals={len(signals)}[{s_src}] cells={len(heatmap.get('cells',[]))}[{h_src}] history={len(history)}[{p_src}]")
        except Exception as e:
            _log(f"ERROR {e}")
        time.sleep(3)

if __name__ == "__main__":
    main()
