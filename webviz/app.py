from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
import os, csv, time, glob, json

app = FastAPI(title="scalp-webviz")

BASE = "/opt/scalp/webviz"
DASH = "/opt/scalp/var/dashboard"
KLINES = "/opt/scalp/data/klines"

# ---------- Fichiers statiques ----------
@app.get("/", include_in_schema=False)
def index():
    return FileResponse(os.path.join(BASE, "index.html"))

@app.get("/app.js", include_in_schema=False)
def js():
    return FileResponse(os.path.join(BASE, "app.js"))

@app.get("/style.css", include_in_schema=False)
def css():
    path = os.path.join(BASE, "style.css")
    if os.path.exists(path):
        return FileResponse(path)
    return PlainTextResponse("/* no style.css */", media_type="text/css")

@app.get("/hello", include_in_schema=False)
def hello():
    return PlainTextResponse("hello from rtviz")

# ---------- API Signals ----------
@app.get("/signals")
def get_signals(limit: int = 200):
    path = os.path.join(DASH, "signals_f.csv")
    if not os.path.exists(path):
        return JSONResponse([])
    rows = []
    with open(path, newline="") as f:
        r = csv.reader(f)
        for rec in r:
            try:
                ts, sym, tf, side, rsi, sma, ema, score = rec
                rows.append({
                    "ts": int(ts),
                    "sym": sym,
                    "tf": tf,
                    "side": side,
                    "rsi": float(rsi),
                    "sma": float(sma),
                    "ema": float(ema),
                    "score": float(score),
                })
            except Exception:
                continue
    rows = sorted(rows, key=lambda x: x["ts"], reverse=True)
    return JSONResponse(rows[:limit])

# ---------- API Heatmap ----------
@app.get("/heatmap")
def get_heatmap():
    path = os.path.join(DASH, "signals_f.csv")
    if not os.path.exists(path):
        return JSONResponse({})
    heatmap = {}
    with open(path, newline="") as f:
        r = csv.reader(f)
        for ts, sym, tf, side, rsi, sma, ema, score in r:
            heatmap.setdefault(sym, {})[tf] = {
                "side": side,
                "score": float(score),
                "ts": int(ts)
            }
    return JSONResponse(heatmap)

# ---------- API Historique ----------
@app.get("/history/{symbol}")
def get_history(symbol: str, limit: int = 1000):
    path = os.path.join(DASH, "signals_f.csv")
    if not os.path.exists(path):
        return JSONResponse([])
    rows = []
    with open(path, newline="") as f:
        r = csv.reader(f)
        for rec in r:
            try:
                ts, sym, tf, side, rsi, sma, ema, score = rec
                if sym == symbol:
                    rows.append({
                        "ts": int(ts),
                        "tf": tf,
                        "side": side,
                        "rsi": float(rsi),
                        "sma": float(sma),
                        "ema": float(ema),
                        "score": float(score),
                    })
            except Exception:
                continue
    rows = sorted(rows, key=lambda x: x["ts"], reverse=True)
    return JSONResponse(rows[:limit])

# ---------- API Data (état des fichiers klines) ----------
@app.get("/api/data_status")
def data_status():
    os.makedirs(KLINES, exist_ok=True)
    now = time.time()
    status = {}
    for file in glob.glob(os.path.join(KLINES, "*.csv")):
        base = os.path.basename(file)
        try:
            sym, tfcsv = base.replace(".csv", "").split("_")
            tf = tfcsv.replace("m", "m")  # garde 1m, 5m, 15m, etc.
        except Exception:
            continue

        # état par défaut
        color = "grey"
        mtime = os.path.getmtime(file)
        age = now - mtime

        # règles de fraîcheur
        if tf == "1m" and age < 120:
            color = "green"
        elif tf == "1m" and age < 600:
            color = "orange"
        elif tf == "5m" and age < 600:
            color = "green"
        elif tf == "5m" and age < 1800:
            color = "orange"
        elif tf == "15m" and age < 1800:
            color = "green"
        elif tf == "15m" and age < 3600:
            color = "orange"
        else:
            color = "red"

        sym_clean = sym.replace("USDT", "")
        status.setdefault(sym_clean, {})[tf] = color

    return JSONResponse(status)
