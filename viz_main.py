from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from starlette.staticfiles import StaticFiles
import asyncio

from webviz.realtimeviz.api import router as viz_router, broadcaster, send_test_signal
from webviz.realtimeviz.heatmap import router as heatmap_router

app = FastAPI(title="SCALP - Realtime Visualization")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# API temps réel + Heatmap sous /viz
app.include_router(viz_router, prefix="/viz")
app.include_router(heatmap_router, prefix="/viz")

# Optionnel: static
app.mount("/static", StaticFiles(directory="site"), name="static")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(broadcaster())
    asyncio.create_task(send_test_signal())

@app.get("/", response_model=dict)
def root():
    return {"status": "ok", "service": "scalp-rtviz", "ws": "/viz/ws/stream"}

# Page de test WebSocket
@app.get("/test", response_class=HTMLResponse)
def test_page():
    return """<!doctype html><meta charset="utf-8"><title>WS Test</title>
<body style="font-family:system-ui;margin:20px">
<h1>WS /viz/ws/stream</h1><p id="status">connecting…</p>
<pre id="log" style="background:#111;color:#0f0;padding:10px;height:60vh;overflow:auto"></pre>
<script>
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${proto}://${location.hostname}:${location.port}/viz/ws/stream`);
  const log = m => { const el = document.getElementById('log'); el.textContent += m + "\\n"; el.scrollTop = el.scrollHeight; };
  ws.onopen = ()=> document.getElementById('status').textContent = "connected";
  ws.onmessage = e => log(e.data);
  ws.onclose = ()=> document.getElementById('status').textContent = "closed";
</script>
</body>"""

# -------- Page Heatmap --------
@app.get("/heatmap", response_class=HTMLResponse)
def heatmap_page():
    return """<!doctype html><meta charset="utf-8"><title>Heatmap</title>
<style>
  body{font-family:system-ui;margin:16px}
  .grid{display:grid;grid-template-columns:repeat(5, minmax(120px,1fr));gap:8px}
  .tile{
    border-radius:8px;padding:10px;color:#fff;min-height:72px;
    display:flex;flex-direction:column;justify-content:center;align-items:center;
    box-shadow:0 1px 3px rgba(0,0,0,.2);font-weight:600
  }
  .sym{font-size:14px;opacity:.9}
  .tf{font-size:12px;opacity:.8}
  .score{font-size:20px;margin-top:6px}
</style>
<h1>Heatmap (score -10 ➜ +10)</h1>
<p id="meta" style="color:#666"></p>
<div id="grid" class="grid"></div>
<script>
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
function colorForScore(s){
  // rouge (-10) -> blanc (0) -> vert (+10)
  const t=(s+10)/20; // [0..1]
  const r = s<0 ? 255 : Math.round(255*(1-t));
  const g = s>0 ? 255 : Math.round(255*t);
  const b = s<0 ? Math.round(255*(1+t)) : Math.round(255*(1-t));
  return `rgb(${clamp(r,0,255)},${clamp(g,0,255)},${clamp(b,0,255)})`;
}
async function load(){
  const r = await fetch('/viz/heatmap'); const j = await r.json();
  document.getElementById('meta').textContent = 'as_of: '+ j.as_of;
  const grid = document.getElementById('grid'); grid.innerHTML='';
  // regrouper par (symbol, tf)
  j.cells.sort((a,b)=> (a.symbol+a.tf).localeCompare(b.symbol+b.tf));
  for(const c of j.cells){
    const el = document.createElement('div');
    el.className='tile';
    el.style.background = colorForScore(c.score);
    el.innerHTML = `<div class="sym">${c.symbol}</div>
                    <div class="tf">${c.tf}</div>
                    <div class="score">${c.score.toFixed(1)}</div>`;
    grid.appendChild(el);
  }
}
load(); setInterval(load, 3000);
</script>"""
