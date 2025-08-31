#!/usr/bin/env python3
from fastapi import FastAPI, Request
import time, json, os

app = FastAPI()
QUEUE="/opt/scalp/var/ops/close-requests.ndjson"
os.makedirs(os.path.dirname(QUEUE), exist_ok=True)

@app.post("/api/close")
async def close(req: Request):
    body = await req.json()
    rec = {
        "ts": int(time.time()),
        "symbol": (body.get("symbol") or "").upper(),
        "side": (body.get("side") or "").upper(),   # LONG/SHORT/auto
        "qty": float(body.get("qty") or 0),
        "source": "dashboard"
    }
    with open(QUEUE, "a") as f:
        f.write(json.dumps(rec, separators=(",",":"))+"\n")
    return {"ok": True, "queued": rec}
