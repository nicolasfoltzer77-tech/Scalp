#!/usr/bin/env python3
from __future__ import annotations
import os, csv, json, time
from pathlib import Path
from typing import Any, Dict, List, Tuple
from fastapi import FastAPI, APIRouter, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

VAR_DASH = Path("/opt/scalp/var/dashboard")
CSV_MAIN = VAR_DASH / "signals.csv"
CSV_FACT = VAR_DASH / "signals_f.csv"
HEATMAP_JSON = VAR_DASH / "heatmap.json"
KLINES_DIR = Path("/opt/scalp/data/klines")

app = FastAPI(title="rtviz-ui")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True
)

# ---------- utils ----------
def _safe_int(x: Any, default: int = 0) -> int:
    try: return int(x)
    except Exception:
        try: return int(float(x))
        except Exception: return default

def _load_csv_with_header(path: Path):
    if not path.exists() or path.stat().st_size == 0:
        return [], []
    with path.open("r", encoding="utf-8", newline="") as f:
        lines = [ln.rstrip("\n") for ln in f if ln.strip()]
    if not lines: return [], []
    first = [c.strip() for c in lines[0].split(",")]
    looks_header = any(h.lower() in ("ts","symbol","sym","tf","side","signal","details","rsi","ema","sma","score","entry") for h in first)
    rows = [ [c.strip() for c in ln.split(",")] for ln in (lines[1:] if looks_header else lines) ]
    headers = first if looks_header else []
    return headers, rows

def _parse_row(headers: List[str], row: List[str]) -> Dict[str, Any]:
    out = {"ts":0,"sym":"","tf":"","side":"HOLD","score":"","entry":"","rsi":"","sma":"","ema":""}
    if headers:
        h = {k.lower():i for i,k in enumerate(headers)}
        def g(name,*alts):
            for k in (name,*alts):
                i = h.get(k)
                if i is not None and i < len(row): return row[i]
            return ""
        out["ts"]=_safe_int(g("ts"), int(time.time()))
        out["sym"]=g("symbol","sym")
        out["tf"]=g("tf")
        out["side"]=(g("side","signal") or "HOLD").upper()
        out["score"]=g("score")
        out["entry"]=g("entry")
        out["rsi"]=g("rsi")
        out["sma"]=g("sma","sma_close","sma_price")
        out["ema"]=g("ema","ema_close","ema_price")
        det=g("details")
        if det and not out["rsi"]:
            for part in det.split(";"):
                k,v=(part.split("=",1)+[""])[:2]
                k=k.strip().lower()
                if k=="rsi": out["rsi"]=v
                if k.startswith("sma"): out["sma"]=v
                if k.startswith("ema"): out["ema"]=v
    else:
        if len(row)>=1: out["ts"]=_safe_int(row[0], int(time.time()))
        if len(row)>=2: out["sym"]=row[1]
        if len(row)>=3: out["tf"]=row[2]
        if len(row)>=4: out["side"]=(row[3] or "HOLD").upper()
        if len(row)>=5: out["rsi"]=row[4]
        if len(row)>=6: out["sma"]=row[5]
        if len(row)>=7: out["ema"]=row[6]
        if len(row)>=8: out["score"]=row[7]
        if len(row)>=9: out["entry"]=row[8]
    return out

def _load_signals():
    path = CSV_FACT if CSV_FACT.exists() and CSV_FACT.stat().st_size>0 else CSV_MAIN
    headers, rows = _load_csv_with_header(path)
    return [_parse_row(headers, r) for r in rows]

# ---------- routes de base (sans préfixe) ----------
router = APIRouter()

@router.get("/hello")
def hello():
    return PlainTextResponse("hello from rtviz")

@router.get("/signals")
def signals(limit: int = Query(200, ge=1, le=5000)):
    rows = _load_signals()
    rows.sort(key=lambda x: x.get("ts",0), reverse=True)
    return JSONResponse(rows[:limit])

@router.get("/history/{sym}")
def history(sym: str, limit: int = Query(500, ge=1, le=10000)):
    sym = sym.upper()
    rows = [r for r in _load_signals() if r.get("sym","").upper()==sym]
    rows.sort(key=lambda x: x.get("ts",0), reverse=True)
    return JSONResponse(rows[:limit])

@router.get("/heatmap")
def heatmap():
    if HEATMAP_JSON.exists() and HEATMAP_JSON.stat().st_size>0:
        try: return JSONResponse(json.loads(HEATMAP_JSON.read_text("utf-8")))
        except Exception: pass
    latest={}
    for r in _load_signals():
        key=(r.get("sym",""), r.get("tf",""))
        if not key[0] or not key[1]: continue
        if key not in latest or r["ts"]>latest[key]["ts"]:
            latest[key]=r
    symbols=sorted({k[0] for k in latest})
    tf_order=["1m","3m","5m","15m","30m","1h","4h","1d"]
    tfs=sorted({k[1] for k in latest}, key=lambda x: tf_order.index(x) if x in tf_order else 999)
    cells=[]
    for s in symbols:
        row={"sym":s}
        for tf in tfs:
            row[tf]=latest.get((s,tf),{}).get("side","")
        cells.append(row)
    return JSONResponse({"symbols":symbols,"tfs":tfs,"cells":cells})

@router.get("/data_status")
def data_status():
    thresholds={"1m":120,"5m":600,"15m":1800}
    now=time.time()
    out={}
    if KLINES_DIR.exists():
        for p in KLINES_DIR.glob("*_*.csv"):
            if "_" not in p.name: continue
            sym, tfext = p.name.rsplit("_",1)
            tf=tfext.replace(".csv","")
            if tf not in thresholds: continue
            age=now-p.stat().st_mtime
            if age<=thresholds[tf]: state="fresh"
            elif age<=thresholds[tf]*3: state="stale"
            else: state="missing"
            out.setdefault(sym, {})[tf]={"state":state,"age_sec":int(age)}
    return JSONResponse(out)

# Monte le même routeur sur "", "/viz" et "/api"
app.include_router(router, prefix="")
app.include_router(router, prefix="/viz")
app.include_router(router, prefix="/api")
