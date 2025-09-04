#!/usr/bin/env python3
from __future__ import annotations
from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse, PlainTextResponse, StreamingResponse
import csv, os, json, asyncio, html
from datetime import datetime, timezone
from typing import List, Dict, Any

app = FastAPI(title="SCALP-rtviz", version="0.5")

CSV_SIGNALS = "/opt/scalp/var/dashboard/signals.csv"

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def parse_ts(v: str) -> int:
    try:
        x = int(float(v))
        return x // 1000 if x > 10**12 else x
    except Exception:
        return 0

def map_row(r: Dict[str,str]) -> Dict[str,Any]:
    # CSV attendu: ts,symbol,tf,signal,details
    return {
        "ts": parse_ts(r.get("ts","0")),
        "sym": r.get("symbol",""),
        "tf": r.get("tf",""),
        "side": r.get("signal",""),
        "score": 0,
        "entry": r.get("details","") or r.get("tf",""),
        "details": r.get("details",""),
    }

def load_csv(limit:int=1000) -> List[Dict[str,Any]]:
    rows: List[Dict[str,Any]] = []
    if not os.path.exists(CSV_SIGNALS):
        return rows
    try:
        with open(CSV_SIGNALS, "r", encoding="utf-8", newline="") as f:
            rdr = csv.DictReader(f)
            for r in rdr:
                rows.append(map_row(r))
    except UnicodeDecodeError:
        # fallback si encodage exotique
        with open(CSV_SIGNALS, "rb") as f:
            txt = f.read().decode("latin-1", errors="ignore")
        rdr = csv.DictReader(txt.splitlines())
        for r in rdr:
            rows.append(map_row(r))
    # derniers d’abord
    rows = rows[-limit:]
    rows.sort(key=lambda x: x["ts"], reverse=True)
    return rows

@app.get("/viz/hello")
def viz_hello(): return {"ok": True, "ver": "rtviz-0.5", "ts": now_iso()}

@app.get("/viz/test")
def viz_test(): return {"ok": True, "ver": "rtviz-0.5", "ts": now_iso()}

# --- API attendue par la UI (toujours un objet {items:[...]})
@app.get("/api/signals")
def api_signals(): return JSONResponse({"items": load_csv(limit=200)})

@app.get("/api/history")
def api_history(): return JSONResponse({"items": load_csv(limit=1000)})

# Alias compat si quelque chose consomme un tableau brut (diagnostic)
@app.get("/api/signals_raw")
def api_signals_raw(): return JSONResponse(load_csv(limit=200))

@app.get("/viz/heatmap")
def viz_heatmap(): return {"cells": []}

@app.get("/viz/stream")
async def viz_stream():
    async def gen():
        while True:
            yield "data: " + json.dumps({"items": load_csv(limit=200)}) + "\n\n"
            await asyncio.sleep(3)
    return StreamingResponse(gen(), media_type="text/event-stream")

# --- Page démo ultra simple (pas de Content-Disposition)
@app.get("/viz/demo")
def viz_demo():
    items = load_csv(limit=200)
    def t(ts:int):
        try: return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        except: return "-"
    rows = "\n".join(
        f"<tr><td>{html.escape(t(it['ts']))}</td>"
        f"<td>{html.escape(it['sym'])}</td>"
        f"<td>{html.escape(it['tf'])}</td>"
        f"<td>{html.escape(it['side'])}</td>"
        f"<td>{html.escape(str(it['entry']))}</td></tr>"
        for it in items
    )
    page = f"""<!doctype html><meta charset="utf-8">
<title>SCALP • Demo</title>
<style>
body{{background:#0b0f14;color:#e7eef7;font:14px system-ui}}
.wrap{{max-width:980px;margin:24px auto}}
h1{{font-size:18px;margin:0 0 12px}}
table{{width:100%;border-collapse:collapse;border:1px solid #1f2a37}}
th,td{{padding:8px 10px;border-bottom:1px solid #1f2a37;white-space:nowrap}}
th{{text-align:left;background:#121924;color:#9fb3c8;position:sticky;top:0}}
tr:hover td{{background:#121924}}
.btn{{display:inline-block;margin:0 6px;padding:6px 10px;background:#1e293b;border:1px solid #2b384b;border-radius:6px;color:#e7eef7;text-decoration:none}}
</style>
<div class="wrap">
  <h1>SCALP • Demo (auto-refresh 5s)</h1>
  <p>
    <a class="btn" href="/viz/hello">/viz/hello</a>
    <a class="btn" href="/api/signals">/api/signals</a>
    <a class="btn" href="#" onclick="location.reload();return false;">↻ Refresh</a>
  </p>
  <table>
    <thead><tr><th>ts (UTC)</th><th>sym</th><th>tf</th><th>side</th><th>entry/details</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>
<script>setTimeout(()=>location.reload(),5000)</script>"""
    return HTMLResponse(page)
