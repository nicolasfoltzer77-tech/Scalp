#!/usr/bin/env python3
from __future__ import annotations
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from datetime import datetime, timezone
import asyncio, json, typing as t

# Adapter (lit nos JSON déjà remplis)
from webviz.realtimeviz.adapter import (
    sources_info,
    get_signals_snapshot,
    get_history_snapshot,
    get_heatmap_cells,
)

app = FastAPI(title="SCALP-rtviz", version="0.4")

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _normalize_signal(x: dict) -> dict:
    """
    Uniformise les clés pour l'UI :
    - 'symbol' -> 'sym'
    - valeurs par défaut pour 'score' et 'entry'
    - garde 'side' tel quel (HOLD compris)
    """
    y = dict(x)
    if "sym" not in y and "symbol" in y:
        y["sym"] = y.pop("symbol")
    y.setdefault("score", 0)
    y.setdefault("entry", None)
    # ts au format ISO si fourni en epoch
    ts = y.get("ts")
    if isinstance(ts, (int, float)) and ts > 1e10:  # ms epoch
        y["ts"] = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()
    elif isinstance(ts, (int, float)):             # s epoch
        y["ts"] = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    return y

def _sse_pack(data: dict, event: str | None = None) -> bytes:
    payload = json.dumps(data, separators=(",", ":"))
    head = f"event: {event}\n" if event else ""
    return (head + f"data: {payload}\n\n").encode("utf-8")

@app.get("/viz/hello")
def viz_hello():
    return {"ok": True, "ver": "rtviz-0.4", "ts": now_iso()}

@app.get("/viz/test")
def viz_test():
    return {"ok": True, "ver": "rtviz-0.4", "ts": now_iso(), "src": sources_info()}

# --- API consommée par la page ---
@app.get("/api/signals")
def api_signals():
    snap = get_signals_snapshot(limit=200, include_hold=True)   # << HOLD visible
    items = [ _normalize_signal(x) for x in snap.get("items", []) ]
    return JSONResponse({"items": items})

@app.get("/api/history")
def api_history():
    snap = get_history_snapshot(limit=1000)
    items = [ _normalize_signal(x) for x in snap.get("items", []) ]
    return JSONResponse({"items": items})

@app.get("/viz/heatmap")
def viz_heatmap():
    return JSONResponse(get_heatmap_cells())

# --- Flux temps réel (SSE) optionnel ---
@app.get("/viz/stream")
async def viz_stream():
    async def gen():
        while True:
            snap = get_signals_snapshot(limit=200, include_hold=True)
            items = [ _normalize_signal(x) for x in snap.get("items", []) ]
            yield _sse_pack({"items": items}, event="signals")
            await asyncio.sleep(3)
    return StreamingResponse(gen(), media_type="text/event-stream")
