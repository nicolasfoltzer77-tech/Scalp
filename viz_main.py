import os, time, asyncio, json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

VERSION = "rtviz-0.7"

DATA_DIR = "/opt/scalp/var/dashboard"
CSV_FILE = os.path.join(DATA_DIR, "signals.csv")
JSON_SIGNALS = os.path.join("/opt/scalp/data", "signals.json")
JSON_HISTORY = os.path.join("/opt/scalp/data", "history.json")
JSON_HEATMAP = os.path.join("/opt/scalp/data", "heatmap.json")


# --- helpers ---
def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return default


# --- endpoints ---
@app.get("/viz/test")
async def viz_test():
    return {"ok": True, "ver": VERSION}


@app.get("/api/signals_raw")
async def api_signals_raw(limit: int = 100):
    items = []
    try:
        with open(CSV_FILE) as f:
            header = f.readline().strip().split(",")
            for line in f:
                row = dict(zip(header, line.strip().split(",")))
                items.append(row)
    except Exception as e:
        return {"error": str(e), "items": []}
    return items[:limit]


@app.get("/api/signals")
async def api_signals(limit: int = 100, include_hold: bool = False):
    raw = await api_signals_raw(limit=1000)
    if isinstance(raw, dict) and "error" in raw:
        return raw
    items = []
    for row in raw:
        sig = row.get("signal", "")
        if not include_hold and sig.upper() == "HOLD":
            continue
        items.append({
            "ts": int(row.get("ts", "0")),
            "sym": row.get("symbol", ""),
            "tf": row.get("tf", ""),
            "side": sig,
            "entry": row.get("details", ""),
            "score": 0,
        })
    return {"total": len(items), "items": items[:limit]}


@app.get("/api/history")
async def api_history():
    return load_json(JSON_HISTORY, {"total": 0, "items": []})


@app.get("/viz/heatmap")
async def viz_heatmap():
    return load_json(JSON_HEATMAP, {"source": "fallback", "cells": []})


@app.get("/viz/stream")
async def viz_stream(request: Request):
    async def eventgen():
        while True:
            if await request.is_disconnected():
                break
            yield f"data: ping {int(time.time())}\n\n"
            await asyncio.sleep(5)
    return StreamingResponse(eventgen(), media_type="text/event-stream")


# --- UI demo ---
@app.get("/viz/demo")
async def viz_demo():
    html = """
    <html>
    <head><title>SCALP • Demo</title></head>
    <body>
      <h3>SCALP • Demo (auto-refresh 5s)</h3>
      <div id="out">loading…</div>
      <script>
      async function refresh(){
        let r = await fetch('/api/signals?include_hold=true&limit=10');
        let j = await r.json();
        document.getElementById('out').innerHTML =
          '<pre>'+JSON.stringify(j,null,2)+'</pre>';
      }
      setInterval(refresh, 5000);
      refresh();
      </script>
    </body>
    </html>
    """
    return HTMLResponse(html)


# --- main ---
if __name__ == "__main__":
    uvicorn.run("viz_main:app", host="0.0.0.0", port=8100, reload=False)
