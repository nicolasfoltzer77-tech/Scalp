#!/usr/bin/env python3
import os, json
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

BASE = "/opt/scalp/webviz"
STATIC = os.path.join(BASE)
DATA_STATUS_FILE = "/opt/scalp/var/dashboard/data_status.json"

app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")


@app.get("/hello")
async def hello():
    return "hello from rtviz"


@app.get("/signals")
async def signals():
    path = "/opt/scalp/var/dashboard/signals_f.csv"
    if not os.path.exists(path):
        return []
    with open(path) as f:
        rows = [l.strip().split(",") for l in f if l.strip()]
    return [
        {
            "ts": r[0],
            "sym": r[1],
            "tf": r[2],
            "side": r[3],
            "score": r[4] if len(r) > 4 else "",
            "entry": r[5] if len(r) > 5 else "",
        }
        for r in rows
    ]


@app.get("/heatmap")
async def heatmap():
    path = "/opt/scalp/var/dashboard/heatmap.json"
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


@app.get("/data_status")
async def data_status():
    if not os.path.exists(DATA_STATUS_FILE):
        return JSONResponse(content={"error": "data_status.json not found"}, status_code=404)
    with open(DATA_STATUS_FILE) as f:
        return json.load(f)
