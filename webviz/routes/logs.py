from fastapi import APIRouter
from fastapi.responses import HTMLResponse
router = APIRouter()

T = """<!doctype html><meta charset="utf-8"><title>{title}</title>
<style>body{background:#0f141b;color:#d7e1ec;font-family:system-ui,Segoe UI,Roboto,Arial,sans-serif}
pre{white-space:pre-wrap;background:#0b1117;border:1px solid #223;border-radius:8px;padding:10px}
a{color:#7ab9ff;text-decoration:none}</style>
<h3>{title}</h3>
<div>Sources: <code>{src}</code></div>
<pre id="out">Chargement…</pre>
<script>
async function load(){
  const r=await fetch('{endpoint}'); const js=await r.json();
  document.querySelector('#out').textContent = JSON.stringify(js,null,2);
}
load();</script>"""

def page(title, endpoint, src=""):
    return HTMLResponse(T.format(title=title, endpoint=endpoint, src=src))

@router.get("/logs/signals")
def logs_signals():
    return page("Logs • Signals", "/api/signals_status", "csv/json")

@router.get("/logs/history")
def logs_history():
    return page("Logs • History", "/api/history_status", "history.json")

@router.get("/logs/heatmap")
def logs_heatmap():
    return page("Logs • Heatmap", "/viz/heatmap_status", "heatmap.json / fallback signals")

@router.get("/logs/stream")
def logs_stream():
    return page("Logs • Stream (SSE)", "/viz/stream_status", "signals.csv")
