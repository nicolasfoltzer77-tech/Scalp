# /opt/scalp/viz_main.py
from __future__ import annotations
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from datetime import datetime, timezone
import asyncio, json

from webviz.realtimeviz.adapter import (
    get_watchlist_snapshot, get_signals_snapshot, sources_info
)

app = FastAPI(title="SCALP-rtviz", version="0.4")

def now_iso(): return datetime.now(timezone.utc).isoformat()
def sse_pack(data: dict, event: str | None = None) -> bytes:
    payload = json.dumps(data, separators=(",", ":"))
    head = f"event: {event}\n" if event else ""
    return (head + f"data: {payload}\n\n").encode("utf-8")

@app.get("/viz/hello")
def hello(): return {"ok": True, "msg": "hello from viz", "ts": now_iso()}

@app.get("/viz/test")
def test(): return {"ok": True, "ver": "rtviz-0.4", "ts": now_iso()}

@app.get("/viz/heatmap")
def heatmap(): return JSONResponse(get_watchlist_snapshot())

@app.get("/viz/sources")
def sources(): return sources_info()

# --- SSE ----------------------------------------------------------------------
clients: set[asyncio.Queue[bytes]] = set()
publisher_task: asyncio.Task | None = None

@app.on_event("startup")
async def _startup():
    async def publisher():
        while True:
            # HEATMAP
            hm = get_watchlist_snapshot()
            frame = sse_pack({"type": "heatmap", "data": hm}, event="heatmap")
            for q in list(clients): q.put_nowait(frame)
            # SIGNAUX
            for sig in (get_signals_snapshot() or []):
                frame = sse_pack({"type": "signal", "data": sig}, event="signal")
                for q in list(clients): q.put_nowait(frame)
            # TICK
            for q in list(clients): q.put_nowait(sse_pack({"type":"tick","ts":now_iso()}, event="tick"))
            await asyncio.sleep(3)
    global publisher_task
    publisher_task = asyncio.create_task(publisher())

@app.on_event("shutdown")
async def _shutdown():
    if publisher_task: publisher_task.cancel()

@app.get("/viz/stream")
async def stream():
    q: asyncio.Queue[bytes] = asyncio.Queue()
    clients.add(q)
    async def gen():
        try:
            yield sse_pack({"type": "hello", "ts": now_iso()}, event="hello")
            while True:
                yield await q.get()
        finally:
            clients.discard(q)
    headers = {"Cache-Control":"no-cache","Connection":"keep-alive","X-Accel-Buffering":"no"}
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)
