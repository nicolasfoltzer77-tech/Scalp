#!/usr/bin/env python3
from __future__ import annotations
import os, csv, json, time
from pathlib import Path
from typing import Any, Dict, List, Tuple
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

# === Chemins locaux ===
VAR_DASH = Path("/opt/scalp/var/dashboard")
CSV_MAIN = VAR_DASH / "signals.csv"          # CSV “classique”
CSV_FACT = VAR_DASH / "signals_f.csv"        # CSV factorisé (si présent, on le préfère)
HEATMAP_JSON = VAR_DASH / "heatmap.json"     # heatmap (si présente)
KLINES_DIR = Path("/opt/scalp/data/klines")  # fichiers klines *_<tf>.csv

app = FastAPI(title="rtviz-ui backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True
)

# --- Utils de lecture sûrs ----------------------------------------------------
def _safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        try:
            return int(float(x))
        except Exception:
            return default

def _load_csv_with_header(path: Path) -> Tuple[List[str], List[List[str]]]:
    """Lit un CSV (avec ou sans header). Retourne (headers, rows_str)."""
    if not path.exists() or path.stat().st_size == 0:
        return [], []
    with path.open("r", encoding="utf-8", newline="") as f:
        lines = [ln.rstrip("\n") for ln in f if ln.strip() != ""]
    if not lines:
        return [], []
    # Détecte header: contient des colonnes non-numériques “connues” ?
    first = [c.strip() for c in lines[0].split(",")]
    looks_like_header = any(h.lower() in ("ts","symbol","sym","tf","side","signal","details","rsi","ema","sma","score","entry") for h in first)
    rows = [ [c.strip() for c in ln.split(",")] for ln in (lines[1:] if looks_like_header else lines) ]
    headers = first if looks_like_header else []
    return headers, rows

def _parse_signals_row(headers: List[str], row: List[str]) -> Dict[str, Any]:
    """Normalise une ligne en dict {ts,sym,tf,side,score,entry,rsi,sma,ema}."""
    out: Dict[str, Any] = {"ts":0,"sym":"","tf":"","side":"HOLD","score":"","entry":"","rsi":"","sma":"","ema":""}
    if headers:
        hmap = {h.lower():i for i,h in enumerate(headers)}
        # champs “souples”
        def g(name: str, alt: List[str]) -> str:
            for k in [name,*alt]:
                i = hmap.get(k)
                if i is not None and i < len(row): return row[i]
            return ""
        out["ts"]   = _safe_int(g("ts", []), int(time.time()))
        out["sym"]  = g("symbol", ["sym"])
        out["tf"]   = g("tf", [])
        side        = g("side", ["signal"]).upper() or "HOLD"
        out["side"] = side
        out["score"]= g("score", [])
        out["entry"]= g("entry", [])
        out["rsi"]  = g("rsi", [])
        out["sma"]  = g("sma", ["sma_close","sma_price"])
        out["ema"]  = g("ema", ["ema_close","ema_price"])
        if not out["rsi"] and g("details", []):
            # Essaie d’extraire des “details=key=val;...” si présent
            det = g("details", [])
            for part in det.split(";"):
                k,v = (part.split("=",1)+[""])[:2]
                k=k.strip().lower()
                if k=="rsi": out["rsi"]=v
                if k.startswith("sma"): out["sma"]=v
                if k.startswith("ema"): out["ema"]=v
    else:
        # Pas de header : on devine l’ordre le plus courant
        # ts,symbol,tf,side,(rsi),(sma),(ema),(score),(entry)  => on remplit ce qu’on peut
        if len(row) >= 1: out["ts"]   = _safe_int(row[0], int(time.time()))
        if len(row) >= 2: out["sym"]  = row[1]
        if len(row) >= 3: out["tf"]   = row[2]
        if len(row) >= 4: out["side"] = (row[3] or "HOLD").upper()
        if len(row) >= 5: out["rsi"]  = row[4]
        if len(row) >= 6: out["sma"]  = row[5]
        if len(row) >= 7: out["ema"]  = row[6]
        if len(row) >= 8: out["score"]= row[7]
        if len(row) >= 9: out["entry"]= row[8]
    return out

def _load_signals() -> List[Dict[str,Any]]:
    """Charge signals_f.csv si présent sinon signals.csv; reconstruit dicts normés."""
    path = CSV_FACT if CSV_FACT.exists() and CSV_FACT.stat().st_size>0 else CSV_MAIN
    headers, rows = _load_csv_with_header(path)
    return [_parse_signals_row(headers, r) for r in rows]

# --- Routes API ---------------------------------------------------------------

@app.get("/hello")
def hello() -> PlainTextResponse:
    return PlainTextResponse("hello from rtviz")

@app.get("/signals")
def get_signals(limit: int = Query(200, ge=1, le=5000)) -> JSONResponse:
    rows = _load_signals()
    rows.sort(key=lambda x: x.get("ts",0), reverse=True)
    return JSONResponse(rows[:limit])

@app.get("/history/{sym}")
def get_history(sym: str, limit: int = Query(500, ge=1, le=10000)) -> JSONResponse:
    sym = sym.upper()
    rows = [r for r in _load_signals() if (r.get("sym","").upper()==sym)]
    rows.sort(key=lambda x: x.get("ts",0), reverse=True)
    return JSONResponse(rows[:limit])

@app.get("/heatmap")
def get_heatmap() -> JSONResponse:
    # 1) heatmap.json si présent
    if HEATMAP_JSON.exists() and HEATMAP_JSON.stat().st_size>0:
        try:
            return JSONResponse(json.loads(HEATMAP_JSON.read_text("utf-8")))
        except Exception:
            pass
    # 2) fallback depuis les derniers signaux (dernier side par (sym,tf))
    latest: Dict[Tuple[str,str], Dict[str,Any]] = {}
    for r in _load_signals():
        key = (r.get("sym",""), r.get("tf",""))
        if not key[0] or not key[1]: continue
        if key not in latest or r.get("ts",0) > latest[key].get("ts",0):
            latest[key] = r
    # fabrique une grille simple
    symbols = sorted(set(k[0] for k in latest.keys()))
    tfs     = sorted(set(k[1] for k in latest.keys()),
                     key=lambda x: ["1m","3m","5m","15m","30m","1h","4h","1d"].index(x) if x in ["1m","3m","5m","15m","30m","1h","4h","1d"] else 999)
    cells = []
    for s in symbols:
        row = {"sym": s}
        for tf in tfs:
            side = latest.get((s,tf),{}).get("side","")
            row[tf] = side or ""
        cells.append(row)
    return JSONResponse({"symbols":symbols, "tfs":tfs, "cells":cells})

@app.get("/data_status")
def data_status() -> JSONResponse:
    """
    Inspecte /opt/scalp/data/klines/*_{tf}.csv et retourne l’état par symbole/tf.
    Règles fraîcheur:
      1m -> 120s, 5m -> 600s, 15m -> 1800s
    """
    thresholds = {"1m":120, "5m":600, "15m":1800}
    now = time.time()
    out: Dict[str, Dict[str, Dict[str,str]]] = {}
    if not KLINES_DIR.exists():
        return JSONResponse(out)

    for p in KLINES_DIR.glob("*_*.csv"):
        name = p.name  # ex: BTCUSDT_1m.csv
        if "_" not in name: continue
        sym, tf_ext = name.rsplit("_", 1)
        tf = tf_ext.replace(".csv","")
        if tf not in thresholds: continue
        age = now - p.stat().st_mtime
        # état
        if age <= thresholds[tf]:   state = "fresh"
        elif age <= thresholds[tf]*3: state = "stale"
        else:                        state = "missing"
        base = sym  # affichage sans suffixe USDT si tu préfères côté front
        out.setdefault(base, {})[tf] = {"state": state, "age_sec": int(age)}
    return JSONResponse(out)
