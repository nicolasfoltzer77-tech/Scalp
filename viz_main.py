#!/usr/bin/env python3
from __future__ import annotations
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
import csv, os, json, asyncio, html
from datetime import datetime, timezone
from typing import List, Dict

app = FastAPI(title="SCALP-rtviz", version="0.5")

CSV_SIGNALS = "/opt/scalp/var/dashboard/signals.csv"

def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _map_row(r: Dict) -> Dict:
    # ts du CSV → epoch seconds (int)
    raw_ts = r.get("ts", "0")
    try:
        ts = int(float(raw_ts))
        if ts > 10**12:  # si en ms, on convertit
            ts //= 1000
    except Exception:
        ts = 0
    return {
        # schéma attendu par l’UI
        "ts": ts,
        "sym": r.get("symbol",""),
        "side": r.get("signal",""),
        "score": 0,
        "entry": r.get("details","") or r.get("tf",""),
        # extras
        "tf": r.get("tf",""),
        "details": r.get("details",""),
    }

def _load_csv(limit:int=2000) -> List[Dict]:
    if not os.path.exists(CSV_SIGNALS):
        return []
    rows: List[Dict] = []
    with open(CSV_SIGNALS, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(_map_row(r))
    rows = rows[-limit:]
    rows.sort(key=lambda x: x["ts"], reverse=True)
    return rows

@app.get("/viz/hello")
def viz_hello():
    return {"ok": True, "ver": "rtviz-0.5", "ts": _utcnow_iso()}

@app.get("/viz/test")
def viz_test():
    return {"ok": True, "ver": "rtviz-0.5", "ts": _utcnow_iso()}

# === API utilisées par la UI existante ===
@app.get("/api/signals")
def api_signals():
    return JSONResponse({"items": _load_csv(limit=200)})

@app.get("/api/history")
def api_history():
    return JSONResponse({"items": _load_csv(limit=1000)})

@app.get("/viz/heatmap")
def viz_heatmap():
    # pour l’instant vide; on branchera ensuite la vraie heatmap
    return {"cells": []}

@app.get("/viz/stream")
async def viz_stream():
    # SSE simple : snapshot toutes les 3s
    async def gen():
        while True:
            payload = {"items": _load_csv(limit=200)}
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(3)
    return StreamingResponse(gen(), media_type="text/event-stream")

# === PAGE DEMO (fonctionnelle tout de suite) ===
@app.get("/viz/demo")
def viz_demo():
    items = _load_csv(limit=200)
    def fmt_time(ts:int)->str:
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return "-"
    # petit HTML autonome + auto-refresh 5s
    rows_html = "\n".join(
        f"<tr>"
        f"<td>{html.escape(fmt_time(it['ts']))}</td>"
        f"<td>{html.escape(it['sym'])}</td>"
        f"<td>{html.escape(it['tf'])}</td>"
        f"<td>{html.escape(it['side'])}</td>"
        f"<td style='opacity:.8'>{html.escape(str(it['entry']))}</td>"
        f"</tr>"
        for it in items
    )
    page = f"""<!doctype html>
<html lang="fr">
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>SCALP • Demo Signals</title>
<style>
body{{background:#0b0f14;color:#e7eef7;font:14px/1.4 system-ui,Segoe UI,Roboto,Helvetica,Arial}}
h1{{font-size:18px;margin:16px 12px}}
small{{color:#9fb3c8}}
.container{{margin:12px}}
table{{width:100%;border-collapse:collapse;background:#0f141b;border:1px solid #1f2a37;border-radius:8px;overflow:hidden}}
th,td{{padding:8px 10px;border-bottom:1px solid #1f2a37;white-space:nowrap}}
th{{text-align:left;color:#9fb3c8;font-weight:600;background:#121924;position:sticky;top:0}}
tr:hover td{{background:#121924}}
.badge{{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px}}
.badge.HOLD{{background:#2a3342;color:#9fb3c8}}
.badge.BUY{{background:#0f5132;color:#9ff1c6}}
.badge.SELL{{background:#5b1a1a;color:#ffd5d5}}
.topbar{{display:flex;gap:8px;align-items:center;margin:8px 12px}}
.btn{{background:#1e293b;color:#e7eef7;border:1px solid #2b384b;border-radius:8px;padding:8px 10px;cursor:pointer}}
.btn:hover{{background:#243347}}
</style>
<div class="topbar">
  <h1>SCALP • Demo Signals <small>(auto-refresh 5s)</small></h1>
  <button class="btn" onclick="location.reload()">↻ Refresh</button>
  <a class="btn" href="/viz/hello">/viz/hello</a>
  <a class="btn" href="/api/signals">/api/signals</a>
</div>
<div class="container">
  <table>
    <thead><tr><th>ts (UTC)</th><th>sym</th><th>tf</th><th>side</th><th>entry/details</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>
<script>
  setTimeout(()=>location.reload(),5000);
  // colorise les badges côté client
  for (const td of document.querySelectorAll('tbody tr td:nth-child(4)')) {{
    const s = td.textContent.trim();
    td.innerHTML = `<span class="badge ${s}">${{s||'-'}}</span>`;
  }}
</script>
</html>"""
    return HTMLResponse(page)
