# /opt/scalp/viz_main.py
from __future__ import annotations
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from datetime import datetime, timezone
import asyncio, json, os

APP_VER = "rtviz-0.4"

DATA_DIR   = "/opt/scalp/data"
REPORT_DIR = "/opt/scalp/reports"

PATH_SIGNALS  = f"{DATA_DIR}/signals.json"
PATH_HISTORY  = f"{DATA_DIR}/history.json"
PATH_HEATMAP  = f"{DATA_DIR}/heatmap.json"
PATH_WATCH_JS = f"{REPORT_DIR}/watchlist.json"
PATH_POS_JS   = f"{REPORT_DIR}/positions.json"

app = FastAPI(title="SCALP-rtviz", version=APP_VER)

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def read_json(path: str, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default

def sse_pack(data: dict, event: str | None = None) -> bytes:
    head = f"event: {event}\n" if event else ""
    payload = json.dumps(data, separators=(",", ":"))
    return (head + f"data: {payload}\n\n").encode("utf-8")

def get_signals_snapshot(limit: int = 200, include_hold: bool = True) -> dict:
    raw = read_json(PATH_SIGNALS, {"items": []})
    items = raw if isinstance(raw, list) else raw.get("items", [])
    # items peut être une liste brute (CSV->JSON) ou un dict {items:[...]}
    if not isinstance(items, list):
        items = []
    if not include_hold:
        items = [it for it in items if str(it.get("side","")).upper() != "HOLD"]
    return {"as_of": now_iso(), "items": items[:limit]}

def get_history_snapshot(limit: int = 1000) -> dict:
    raw = read_json(PATH_HISTORY, {"items": []})
    items = raw if isinstance(raw, list) else raw.get("items", [])
    if not isinstance(items, list):
        items = []
    return {"as_of": now_iso(), "items": items[:limit]}

def get_watchlist_snapshot() -> dict:
    raw = read_json(PATH_WATCH_JS, {"items": []})
    items = raw if isinstance(raw, list) else raw.get("items", [])
    if not isinstance(items, list):
        items = []
    return {"as_of": now_iso(), "items": items}

def get_positions_snapshot() -> dict:
    raw = read_json(PATH_POS_JS, {"items": []})
    items = raw if isinstance(raw, list) else raw.get("items", [])
    if not isinstance(items, list):
        items = []
    return {"as_of": now_iso(), "items": items}

def get_heatmap() -> dict:
    raw = read_json(PATH_HEATMAP, {"cells": []})
    # accepter soit {"cells":[...]} soit liste brute
    cells = raw if isinstance(raw, list) else raw.get("cells", [])
    if not isinstance(cells, list):
        cells = []
    return {"as_of": now_iso(), "cells": cells}

@app.get("/viz/hello")
def viz_hello():
    return {"ok": True, "ver": APP_VER, "ts": now_iso()}

@app.get("/viz/test")
def viz_test():
    return {
        "ok": True, "ver": APP_VER, "ts": now_iso(),
        "as_of": now_iso(),
        "files": {
            "signals": PATH_SIGNALS,
            "history": PATH_HISTORY,
            "heatmap": PATH_HEATMAP,
            "watchlist_json": PATH_WATCH_JS,
            "positions_json": PATH_POS_JS,
        },
        "hints": {"produce_here": DATA_DIR, "reports_here": REPORT_DIR}
    }

@app.get("/viz/heatmap")
def viz_heatmap():
    return get_heatmap()

@app.get("/api/signals")
def api_signals():
    return JSONResponse(get_signals_snapshot(limit=200, include_hold=True))

@app.get("/api/history")
def api_history():
    return JSONResponse(get_history_snapshot(limit=1000))

@app.get("/api/watchlist")
def api_watchlist():
    return JSONResponse(get_watchlist_snapshot())

@app.get("/api/positions")
def api_positions():
    return JSONResponse(get_positions_snapshot())

@app.get("/viz/stream")
async def viz_stream():
    async def gen():
        # ping initial
        yield sse_pack({"type": "ping", "ts": now_iso()}, event="ping")
        while True:
            await asyncio.sleep(5)
            # envoie un petit ping + un snapshot signals
            yield sse_pack({"type": "ping", "ts": now_iso()}, event="ping")
            yield sse_pack(get_signals_snapshot(limit=50, include_hold=True), event="signals")
    return StreamingResponse(gen(), media_type="text/event-stream")
