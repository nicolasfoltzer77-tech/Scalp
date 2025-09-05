from __future__ import annotations
import os, json, time, asyncio
from typing import Dict, Any, List
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse, FileResponse

APP_ROOT = "/opt/scalp/webviz"
DASH = "/opt/scalp/var/dashboard"
DATA_JSON = os.path.join(DASH, "data_status.json")

app = FastAPI()

# --------- pages statiques ----------
@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(os.path.join(APP_ROOT, "index.html"))

@app.get("/app.js")
def appjs():
    return FileResponse(os.path.join(APP_ROOT, "app.js"))

# --------- API existantes (extraits) ----------
@app.get("/hello")
def hello():
    return PlainTextResponse("hello from rtviz")

@app.get("/version")
def version():
    ui = {"ui": "1.0.2", "ts": int(time.time())}
    return JSONResponse(ui)

@app.get("/data")
def data_status():
    try:
        with open(DATA_JSON, "r", encoding="utf-8") as f:
            return JSONResponse(json.load(f))
    except Exception:
        return JSONResponse({"symbols": {}, "ts": int(time.time())})

# =====================================================================
#                    🔔 PUSH temps-réel via SSE
# =====================================================================

# Abonnés SSE (une queue asyncio par client)
subscribers: List[asyncio.Queue] = []
prev_snapshot: Dict[str, Any] = {"symbols": {}}
last_mtime: float = 0.0

async def _watch_data_file():
    """Surveille data_status.json, et notifie quand un 1m devient 'fresh'."""
    global prev_snapshot, last_mtime
    while True:
        try:
            m = os.path.getmtime(DATA_JSON)
        except Exception:
            await asyncio.sleep(2)
            continue

        if m != last_mtime:
            last_mtime = m
            try:
                with open(DATA_JSON, "r", encoding="utf-8") as f:
                    cur = json.load(f)
            except Exception:
                cur = {"symbols": {}}

            # détecte les bascules -> fresh (TF 1m uniquement)
            prev_syms = prev_snapshot.get("symbols", {})
            cur_syms  = cur.get("symbols", {})
            for sym, sts in cur_syms.items():
                cur1 = (sts or {}).get("1m")
                prev1 = (prev_syms.get(sym) or {}).get("1m")
                if cur1 == "fresh" and prev1 != "fresh":
                    payload = {"sym": sym, "tf": "1m", "state": "fresh", "ts": int(time.time())}
                    # diffuse à tous les abonnés
                    for q in list(subscribers):
                        try:
                            q.put_nowait(payload)
                        except Exception:
                            pass

            prev_snapshot = cur

        await asyncio.sleep(1.0)  # fréquence de scan

@app.on_event("startup")
async def on_start():
    # amorce le snapshot (si fichier présent)
    global prev_snapshot, last_mtime
    try:
        last_mtime = os.path.getmtime(DATA_JSON)
        with open(DATA_JSON, "r", encoding="utf-8") as f:
            prev_snapshot = json.load(f)
    except Exception:
        prev_snapshot = {"symbols": {}}
    # tâche de surveillance
    asyncio.create_task(_watch_data_file())

@app.get("/data/stream")
async def data_stream(request: Request):
    """
    SSE : envoie un event JSON quand un couple (sym, 1m) devient 'fresh'.
    """
    q: asyncio.Queue = asyncio.Queue()
    subscribers.append(q)

    async def event_gen():
        try:
            # ping initial (garde-fou pour établir la connexion côté navigateur)
            yield "retry: 2000\n\n"
            while True:
                # coupe si client a fermé
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=10.0)
                    data = json.dumps(payload, separators=(",", ":"))
                    yield f"event: one_min_fresh\ndata: {data}\n\n"
                except asyncio.TimeoutError:
                    # keep-alive
                    yield ": keepalive\n\n"
        finally:
            # désinscription
            try:
                subscribers.remove(q)
            except ValueError:
                pass

    headers = {
        "Cache-Control": "no-store",
        "Content-Type": "text/event-stream",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "Access-Control-Allow-Origin": "*",
    }
    return StreamingResponse(event_gen(), headers=headers)
