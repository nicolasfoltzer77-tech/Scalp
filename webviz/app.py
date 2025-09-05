from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
import os, csv, time, glob, json
from collections import defaultdict

app = FastAPI(title="scalp-webviz")

BASE = "/opt/scalp/webviz"
DASH = "/opt/scalp/var/dashboard"   # signals.csv, signals_f.csv, heatmap.json
KLINES = "/opt/scalp/data/klines"

# --------- Static + index ----------
app.mount("/static", StaticFiles(directory=BASE), name="static")

@app.get("/", include_in_schema=False)
def index():
    return FileResponse(os.path.join(BASE, "index.html"))

@app.get("/hello", include_in_schema=False)
def hello():
    return PlainTextResponse("hello from rtviz")

# --------- Helpers ----------
def _read_signals_csv():
    """Lit signals_f.csv si présent, sinon signals.csv → liste de dicts pour l’UI."""
    candidate = os.path.join(DASH, "signals_f.csv")
    if not os.path.exists(candidate):
        candidate = os.path.join(DASH, "signals.csv")
    if not os.path.exists(candidate):
        return []

    rows = []
    with open(candidate, newline="", encoding="utf-8") as f:
        # on regarde l'entête si elle existe
        first = f.readline()
        header = [c.strip() for c in first.strip().split(",")] if first else []
        f.seek(0)
        if "side" in header or "score" in header:
            r = csv.DictReader(f)
            for rec in r:
                try:
                    ts = int(float(rec.get("ts", time.time())))
                except Exception:
                    ts = int(time.time())
                rows.append({
                    "ts": ts,
                    "sym": rec.get("symbol","").replace("USDT",""),
                    "tf": rec.get("tf",""),
                    "side": rec.get("side","HOLD"),
                    "score": float(rec.get("score", 0) or 0),
                    "entry": rec.get("entry",""),
                })
        else:
            r = csv.DictReader(f, fieldnames=["ts","symbol","tf","signal","details"])
            for rec in r:
                try:
                    ts = int(float(rec.get("ts", time.time())))
                except Exception:
                    ts = int(time.time())
                rows.append({
                    "ts": ts,
                    "sym": rec.get("symbol","").replace("USDT",""),
                    "tf": rec.get("tf",""),
                    "side": (rec.get("signal","HOLD") or "HOLD").upper(),
                    "score": 0,
                    "entry": rec.get("details",""),
                })
    return rows[-300:]

def _fallback_heatmap_from_signals(signals):
    """Construit une heatmap minimale à partir des derniers signaux par (sym,tf)."""
    last = {}
    for r in signals:
        key = (r["sym"], r["tf"])
        if key not in last or r["ts"] >= last[key]["ts"]:
            last[key] = r
    cells = []
    for (sym, tf), row in sorted(last.items()):
        side = row.get("side","HOLD")
        v = {"BUY":1.0, "SELL":-1.0}.get(side, 0.0)
        cells.append({"sym": f"{sym}USDT", "tf": tf, "side": side, "v": v})
    return {"source":"fallback(signals)", "cells": cells}

# --------- API: signals ----------
@app.get("/signals")
@app.get("/api/signals")
def get_signals():
    try:
        return _read_signals_csv()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# --------- API: heatmap ----------
@app.get("/heatmap")
@app.get("/api/heatmap")
def get_heatmap():
    try:
        hp = os.path.join(DASH, "heatmap.json")
        if os.path.exists(hp):
            with open(hp, "r", encoding="utf-8") as f:
                return json.load(f)
        # sinon on fabrique depuis les signaux
        return _fallback_heatmap_from_signals(_read_signals_csv())
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# --------- API: état des données (onglet Data) ----------
@app.get("/api/data_status")
def data_status():
    now = time.time()
    status = {}
    for path in glob.glob(os.path.join(KLINES, "*.csv")):
        name = os.path.basename(path).replace(".csv", "")   # ex: BTCUSDT_1m
        try:
            age = now - os.path.getmtime(path)
        except Exception:
            age = None
        if age is None:
            state = "gris"
        elif age < 120:
            state = "vert"
        elif age < 600:
            state = "orange"
        else:
            state = "rouge"
        status[name] = {"file": path, "age_sec": int(age) if age is not None else None, "state": state}
    return status
