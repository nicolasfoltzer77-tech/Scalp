import os, json, time, asyncio
from typing import Optional
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse
from webviz.core.paths import resolve_paths, load_json, parse_signals_csv_lines
from webviz.core.diag import diag_stream

router = APIRouter()

@router.get("/stream_status")
def stream_status():
    return diag_stream()

def _sse_pack(data: str, event: Optional[str]=None, id_: Optional[str]=None) -> str:
    parts=[]
    if event: parts.append(f"event: {event}")
    if id_:  parts.append(f"id: {id_}")
    for line in (data.splitlines() or [""]):
        parts.append(f"data: {line}")
    parts.append("")
    return "\n".join(parts)

async def _gen(request: Request):
    p = resolve_paths()
    counts = {
        "signals.csv": os.path.getsize(p["signals_csv"]) if p["signals_csv"] and os.path.exists(p["signals_csv"]) else None,
        "signals.json": len((load_json(p["signals_json"]) or {}).get("items", [])) if p["signals_json"] else None,
        "history.json": len((load_json(p["history_json"]) or {}).get("items", [])) if p["history_json"] else None,
        "heatmap.json": len((load_json(p["heatmap_json"]) or {}).get("cells", [])) if p["heatmap_json"] else None,
    }
    yield _sse_pack(json.dumps({"ver":"rtviz-1.0","counts":counts}), event="info")
    f=None
    if p["signals_csv"] and os.path.exists(p["signals_csv"]):
        f=open(p["signals_csv"], "r", encoding="utf-8", errors="ignore")
        f.seek(0, os.SEEK_END)
    eid=0
    last_ping=time.time()
    try:
        while True:
            if await request.is_disconnected(): break
            pushed=False
            if f:
                line=f.readline()
                if line:
                    it = parse_signals_csv_lines([line])
                    if it:
                        eid+=1
                        yield _sse_pack(json.dumps(it[0]), event="signal", id_=str(eid))
                        pushed=True
                else:
                    await asyncio.sleep(0.5)
            now=time.time()
            if not pushed and (now-last_ping)>=5:
                eid+=1
                yield _sse_pack(json.dumps({"ping":int(now)}), event="ping", id_=str(eid))
                last_ping=now
    finally:
        if f: f.close()

@router.get("/stream")
async def stream(request: Request):
    return StreamingResponse(_gen(request), media_type="text/event-stream",
        headers={"Cache-Control":"no-cache","Connection":"keep-alive"})
