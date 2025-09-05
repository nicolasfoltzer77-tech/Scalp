from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os, csv, time, glob

app = FastAPI()

BASE = "/opt/scalp/webviz"
CSV_DIR = "/opt/scalp/var/dashboard"
KLINES_DIR = "/opt/scalp/data/klines"

# --- Fichiers statiques ---
app.mount("/static", StaticFiles(directory=BASE), name="static")

@app.get("/")
async def root():
    return FileResponse(os.path.join(BASE, "index.html"))

# --- Endpoint signals (flux principal) ---
@app.get("/signals")
async def signals():
    csv_path = os.path.join(CSV_DIR, "signals.csv")
    if not os.path.exists(csv_path):
        return JSONResponse(content=[], status_code=200)

    rows = []
    with open(csv_path, newline="") as f:
        r = csv.DictReader(f, fieldnames=["ts","symbol","tf","signal","details"])
        for rec in r:
            try:
                ts = int(rec["ts"])
            except Exception:
                ts = int(time.time())
            rows.append({
                "ts": ts,
                "sym": rec["symbol"].replace("USDT",""),
                "tf": rec["tf"],
                "side": rec["signal"],
                "entry": rec.get("details",""),
                "score": 0  # placeholder
            })
    return rows[-200:]  # limiter le flux

# --- Endpoint data_status ---
@app.get("/api/data_status")
async def data_status():
    status = {}
    now = time.time()
    for path in glob.glob(f"{KLINES_DIR}/*.csv"):
        name = os.path.basename(path).replace(".csv","")  # ex: BTCUSDT_1m
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
        status[name] = {"file": path, "age_sec": int(age) if age else None, "state": state}
    return status
