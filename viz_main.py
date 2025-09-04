#!/usr/bin/env python3
from __future__ import annotations
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
import csv, os, asyncio, json
from datetime import datetime, timezone
import typing as t

app = FastAPI(title="SCALP-rtviz", version="0.5")

CSV_SIGNALS = "/opt/scalp/var/dashboard/signals.csv"

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _parse_csv(limit: int = 2000) -> list[dict]:
    rows: list[dict] = []
    if not os.path.exists(CSV_SIGNALS):
        return rows
    with open(CSV_SIGNALS, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                ts = int(row.get("ts", "0"))
                if ts > 1e12:
                    ts = ts / 1000
                row["ts"] = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            except Exception:
                row["ts"] = row.get("ts")
            rows.append(row)
    return rows[-limit:]

@app.get("/viz/test")
def viz_test():
    return {"ok": True, "ver": "rtviz-0.5", "ts": now_iso()}

@app.get("/api/signals")
def api_signals():
    return JSONResponse({"items": _parse_csv(limit=200)})

@app.get("/api/history")
def api_history():
    return JSONResponse({"items": _parse_csv(limit=1000)})

@app.get("/viz/stream")
async def viz_stream():
    async def gen():
        while True:
            yield ("data: " + json.dumps({"items": _parse_csv(limit=200)}) + "\n\n").encode()
            await asyncio.sleep(3)
    return StreamingResponse(gen(), media_type="text/event-stream")
