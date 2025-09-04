# /opt/scalp/viz_main.py — rtviz-0.7
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, HTMLResponse, PlainTextResponse
from fastapi import Request
from typing import List, Dict, Any, Optional
import os, json, csv, time, asyncio

APP_VER = "rtviz-0.7"

DATA_DIR = "/opt/scalp/data"
DASH_DIR = "/opt/scalp/var/dashboard"
PATH_SIGNALS_CSV  = f"{DASH_DIR}/signals.csv"
PATH_SIGNALS_JSON = f"{DATA_DIR}/signals.json"
PATH_HISTORY_JSON = f"{DATA_DIR}/history.json"
PATH_HEATMAP_JSON = f"{DATA_DIR}/heatmap.json"
PATH_WATCHLIST_YAML = "/opt/scalp/reports/watchlist.yml"

app = FastAPI(title="SCALP – Visualisation")

# ---------------- helpers ----------------
def _read_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _file_size(path:str)->int:
    try: return os.stat(path).st_size
    except Exception: return 0

def _read_watchlist() -> List[str]:
    # tolérant: YAML simple ou liste brute
    syms = []
    try:
        with open(PATH_WATCHLIST_YAML, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"): continue
                if line.startswith("- "):
                    syms.append(line[2:].strip().upper())
                elif "," in line and " " not in line:
                    # ligne CSV seule
                    syms += [s.strip().upper() for s in line.split(",")]
    except Exception:
        pass
    # fallback depuis le CSV s’il existe
    if not syms and os.path.exists(PATH_SIGNALS_CSV):
        try:
            with open(PATH_SIGNALS_CSV, "r", encoding="utf-8") as f:
                rdr = csv.DictReader(f)
                ss = set()
                for i, row in enumerate(rdr):
                    s = (row.get("symbol") or row.get("sym") or "").upper()
                    if s: ss.add(s)
                    if len(ss) >= 50: break
                syms = sorted(ss)
        except Exception:
            pass
    return syms

def _signals_from_csv() -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if not os.path.exists(PATH_SIGNALS_CSV):
        return items
    try:
        with open(PATH_SIGNALS_CSV, "r", encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            # headers attendus: ts,symbol,tf,signal,details
            for row in rdr:
                ts_raw = row.get("ts", "")
                try: ts_val = int(ts_raw)
                except Exception: ts_val = ts_raw
                items.append({
                    "ts": ts_val,
                    "sym": (row.get("symbol") or row.get("sym") or "").upper(),
                    "tf": row.get("tf",""),
                    "side": (row.get("signal") or row.get("side") or "").upper(),
                    "score": 0,
                    "entry": row.get("details",""),
                    "details": row.get("details",""),
                })
    except Exception:
        # si fichier en écriture → retenter en lecture simple
        try:
            with open(PATH_SIGNALS_CSV, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
            if lines and "," in lines[0]:
                hdr = [h.strip().lower() for h in lines[0].split(",")]
                for L in lines[1:]:
                    parts = L.split(",", 4)  # details peut contenir des ';'
                    if len(parts) < 5: continue
                    d = dict(zip(hdr, parts))
                    ts_raw = d.get("ts","")
                    try: ts_val = int(ts_raw)
                    except Exception: ts_val = ts_raw
                    items.append({
                        "ts": ts_val,
                        "sym": (d.get("symbol") or d.get("sym") or "").upper(),
                        "tf": d.get("tf",""),
                        "side": (d.get("signal") or d.get("side") or "").upper(),
                        "score": 0,
                        "entry": d.get("details",""),
                        "details": d.get("details",""),
                    })
        except Exception:
            items = []
    return items

def _load_signals_raw() -> List[Dict[str, Any]]:
    # priorité au JSON si valide
    j = _read_json(PATH_SIGNALS_JSON, default=None)
    if isinstance(j, list): return j
    if isinstance(j, dict) and isinstance(j.get("items"), list): return j["items"]
    # fallback CSV
    return _signals_from_csv()

def _paginate(lst: List[Any], limit: int, offset: int):
    total = len(lst)
    if offset < 0: offset = 0
    if limit <= 0: limit = 200
    return total, lst[offset: offset + limit]

# ---------------- endpoints ----------------
@app.get("/viz/test")
def viz_test():
    return {"ok": True, "ver": APP_VER, "sizes": {
        "signals.csv": _file_size(PATH_SIGNALS_CSV),
        "signals.json": _file_size(PATH_SIGNALS_JSON),
        "history.json": _file_size(PATH_HISTORY_JSON),
        "heatmap.json": _file_size(PATH_HEATMAP_JSON),
    }}

# SSE pour apaiser l’UI
@app.get("/viz/stream")
async def viz_stream(request: Request):
    async def eventgen():
        while True:
            if await request.is_disconnected():
                break
            yield f"data: ping {int(time.time())}\n\n"
            await asyncio.sleep(5)
    return PlainTextResponse(eventgen(), media_type="text/event-stream")

@app.get("/api/signals_raw")
def api_signals_raw(limit: int = 200):
    items = _load_signals_raw()
    return items[:max(0, limit)]

@app.get("/api/signals")
def api_signals(
    sym: Optional[str] = Query(None, description="Ex: BTCUSDT,ETHUSDT"),
    tf: Optional[str]  = Query(None, description="Ex: 1m,5m,15m"),
    include_hold: bool = Query(True),   # <-- par défaut on montre les HOLD
    limit: int = 200,
    offset: int = 0,
):
    items = _load_signals_raw()
    # filtres
    if sym:
        allowed = set(s.strip().upper() for s in sym.split(",") if s.strip())
        items = [x for x in items if x.get("sym","").upper() in allowed]
    if tf:
        allowed_tf = set(s.strip() for s in tf.split(",") if s.strip())
        items = [x for x in items if x.get("tf","") in allowed_tf]
    if not include_hold:
        items = [x for x in items if (x.get("side","") or "").upper() != "HOLD"]
    # tri (du plus récent au plus ancien si ts numérique)
    try:
        items.sort(key=lambda x: int(x.get("ts",0)), reverse=True)
    except Exception:
        pass
    total, page = _paginate(items, limit, offset)
    return {"total": total, "items": page}

@app.get("/api/history")
def api_history(limit: int = 1000, offset: int = 0):
    j = _read_json(PATH_HISTORY_JSON, default=None)
    if isinstance(j, dict) and "items" in j and isinstance(j["items"], list):
        base = j["items"]
    elif isinstance(j, list):
        base = j
    else:
        base = []
    total, page = _paginate(base, limit, offset)
    return {"total": total, "items": page}

@app.get("/viz/heatmap")
def viz_heatmap():
    j = _read_json(PATH_HEATMAP_JSON, default=None)
    if isinstance(j, dict) and "cells" in j: return j
    if isinstance(j, list): return {"cells": j, "source": "heatmap.json[list]"}
    syms = _read_watchlist()
    cells = [{"sym": s, "strength": 0.0} for s in syms] if syms else []
    return {"cells": cells, "source": "fallback"}

@app.get("/viz/demo")
def viz_demo():
    html = """
<!doctype html><meta charset="utf-8"><title>SCALP • Demo</title>
<style>
 body{background:#0b0f17;color:#cdd6f4;font:14px/1.35 ui-sans-serif,system-ui}
 table{width:100%;border-collapse:collapse;margin-top:12px}
 th,td{padding:6px 8px;border-bottom:1px solid #1e2633;white-space:nowrap}
 th{position:sticky;top:0;background:#121826}
 .hold{color:#88a}.buy{color:#77f59b}.sell{color:#ff7b7b}
 #bar{display:flex;gap:10px;align-items:center} a,button{color:#7cc4ff}
 button{background:#1a2332;border:1px solid #283245;border-radius:6px;padding:6px 10px}
</style>
<div id="bar">
  <a href="/viz/test">/viz/test</a>
  <a href="/api/signals">/api/signals</a>
  <button onclick="load()">⟳ Refresh</button>
  <span id="info"></span>
</div>
<table id="t"><thead>
  <tr><th>ts (UTC)</th><th>sym</th><th>tf</th><th>side</th><th>entry/details</th></tr>
</thead><tbody></tbody></table>
<script>
async function load(){
  const r = await fetch('/api/signals?include_hold=true&limit=200');
  const j = await r.json();
  const tb = document.querySelector('#t tbody'); tb.innerHTML = '';
  (j.items||[]).forEach(x=>{
    const tr = document.createElement('tr');
    const ts = typeof x.ts==='number' ? new Date(x.ts*1000).toISOString().replace('T',' ').slice(0,19) : x.ts;
    const cls = (x.side||'').toLowerCase()==='buy' ? 'buy' :
                (x.side||'').toLowerCase()==='sell' ? 'sell' : 'hold';
    tr.innerHTML = `<td>${ts||''}</td><td>${x.sym||''}</td><td>${x.tf||''}</td>
                    <td class="${cls}">${x.side||''}</td><td>${x.entry||x.details||''}</td>`;
    tb.appendChild(tr);
  });
  document.getElementById('info').textContent = `total:${j.total||0} • loaded:${(j.items||[]).length}`;
}
load(); setInterval(load, 5000);
</script>"""
    return HTMLResponse(html)

@app.get("/viz/hello")
def viz_hello(): return PlainTextResponse("hello")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("viz_main:app", host="127.0.0.1", port=8100, reload=False)
