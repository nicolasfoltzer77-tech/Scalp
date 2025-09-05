#!/usr/bin/env python3
from __future__ import annotations
import os, json, time
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse, FileResponse, JSONResponse

APP_DIR   = "/opt/scalp/webviz"
DASH_DIR  = "/opt/scalp/var/dashboard"
VERSION   = "1.0.1"   # <— bump

app = FastAPI(title="rtviz-ui", version=VERSION)

def no_cache_headers():
    # empêche le cache navigateur
    return {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}

@app.get("/hello", response_class=PlainTextResponse)
async def hello():
    return "hello from rtviz"

@app.get("/version", response_class=JSONResponse)
async def version():
    return {"ui": VERSION, "ts": int(time.time())}

# Fichiers UI (no-cache)
@app.get("/", response_class=FileResponse)
async def index():
    return FileResponse(os.path.join(APP_DIR, "index.html"), headers=no_cache_headers())

@app.get("/app.js", response_class=FileResponse)
async def appjs():
    return FileResponse(os.path.join(APP_DIR, "app.js"), headers=no_cache_headers())

# APIs existantes (exemples—tu avais déjà /signals, /heatmap)
@app.get("/signals", response_class=PlainTextResponse)
async def signals():
    p = os.path.join(DASH_DIR, "signals.json")
    if not os.path.exists(p):
        return PlainTextResponse('[]', status_code=404)
    return FileResponse(p, headers=no_cache_headers())

@app.get("/heatmap", response_class=PlainTextResponse)
async def heatmap():
    p = os.path.join(DASH_DIR, "heatmap.json")
    if not os.path.exists(p):
        return PlainTextResponse('{"cells":[]}', status_code=404)
    return FileResponse(p, headers=no_cache_headers())

# (le reste de tes routes /logs etc. restent identiques)
