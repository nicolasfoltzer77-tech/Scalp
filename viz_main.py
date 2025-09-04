# /opt/scalp/viz_main.py
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from datetime import datetime, timezone
import asyncio, json, random

app = FastAPI(title="SCALP-rtviz")

# === utils ====================================================================
def now_iso():
    return datetime.now(timezone.utc).isoformat()

def sse_pack(data: dict, event: str | None = None) -> bytes:
    """Format SSE frame."""
    payload = json.dumps(data, separators=(",", ":"))
    head = f"event: {event}\n" if event else ""
    return (head + f"data: {payload}\n\n").encode("utf-8")

# === demo generators (remplace-les par tes vraies sources) =====================
def GEN_heatmap(w=4, h=3):
    cells = []
    for y in range(h):
        for x in range(w):
            v = ((x + y + random.random()) / (w + h))  # 0..1
            cells.append({"x": x, "y": y, "v": round(v, 3)})
    return {"as_of": now_iso(), "cells": cells}

def GEN_signal():
    side = "BUY" if random.random() > 0.5 else "SELL"
    return {
        "id": random.randint(1000, 9999),
        "ts": now_iso(),
        "sym": random.choice(["BTCUSDT", "ETHUSDT", "SOLUSDT"]),
        "side": side,
        "score": round(random.uniform(0.2, 1.0), 2),
        "entry": round(random.uniform(25000, 32000), 2),
    }

# === simple REST (déjà utilisés par le front) =================================
@app.get("/viz/hello")
def hello():
    return {"ok": True, "msg": "hello from viz", "ts": now_iso()}

@app.get("/test")
def test():
    return {"ok": True, "ver": "rtviz-0.2", "ts": now_iso()}

@app.get("/viz/heatmap")
def heatmap():
    return JSONResponse(GEN_heatmap())

# === SSE stream ================================================================
clients: set[asyncio.Queue[bytes]] = set()
publisher_task: asyncio.Task | None = None

@app.on_event("startup")
async def _startup():
    # lance un publisher qui diffuse heatmap + signaux
    async def publisher():
        while True:
            # 1) heatmap toutes les 3s
            hm = GEN_heatmap()
            frame = sse_pack({"type": "heatmap", "data": hm}, event="heatmap")
            for q in list(clients): q.put_nowait(frame)
            # 2) 50% de chances d'envoyer un signal
            if random.random() > 0.5:
                sig = GEN_signal()
                frame = sse_pack({"type": "signal", "data": sig}, event="signal")
                for q in list(clients): q.put_nowait(frame)
            # 3) keep-alive
            ka = sse_pack({"type": "tick", "ts": now_iso()}, event="tick")
            for q in list(clients): q.put_nowait(ka)
            await asyncio.sleep(3)

    global publisher_task
    publisher_task = asyncio.create_task(publisher())

@app.on_event("shutdown")
async def _shutdown():
    if publisher_task: publisher_task.cancel()

@app.get("/viz/stream")
async def stream():
    """
    SSE : text/event-stream
    events: heatmap | signal | tick
    """
    q: asyncio.Queue[bytes] = asyncio.Queue()
    clients.add(q)

    async def gen():
        try:
            # message de bienvenue immédiat
            yield sse_pack({"type": "hello", "ts": now_iso()}, event="hello")
            while True:
                chunk = await q.get()
                yield chunk
        finally:
            clients.discard(q)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # Nginx-like, pas nocif ici
    }
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)
