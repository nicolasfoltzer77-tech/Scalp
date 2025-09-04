# /opt/scalp/viz_main.py  — rtviz-0.6 (no external adapter)
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, HTMLResponse, PlainTextResponse
from typing import List, Dict, Any, Optional
import os, json, csv, time

APP_VER = "rtviz-0.6"

DATA_DIR = "/opt/scalp/data"
DASH_DIR = "/opt/scalp/var/dashboard"
PATH_SIGNALS_CSV  = f"{DASH_DIR}/signals.csv"
PATH_SIGNALS_JSON = f"{DATA_DIR}/signals.json"      # si le service csv2json l’écrit
PATH_HISTORY_JSON = f"{DATA_DIR}/history.json"
PATH_HEATMAP_JSON = f"{DATA_DIR}/heatmap.json"
PATH_WATCHLIST_YAML = "/opt/scalp/reports/watchlist.yml"

app = FastAPI(title="SCALP – Visualisation")

# ---------- helpers sûrs ----------
def _read_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _read_watchlist() -> List[str]:
    # YAML minimal sans dépendance: on prend seulement des lignes '- SYM...'
    syms = []
    try:
        with open(PATH_WATCHLIST_YAML, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("- "):
                    syms.append(line[2:].strip())
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
            for row in rdr:
                # CSV headers attendus: ts,symbol,tf,signal,details
                ts_raw = row.get("ts", "")
                try:
                    ts_val = int(ts_raw)
                except Exception:
                    # ts ISO → on laisse tel quel (UI sait afficher string)
                    ts_val = ts_raw
                items.append({
                    "ts": ts_val,
                    "sym": row.get("symbol",""),
                    "tf": row.get("tf",""),
                    "side": row.get("signal",""),
                    "score": 0,
                    "entry": row.get("details",""),
                    "details": row.get("details",""),
                })
    except Exception:
        # si parsing échoue (fichier en cours d’écriture), on retourne vide
        items = []
    return items

def _load_signals_raw() -> List[Dict[str, Any]]:
    # priorité au JSON si présent et valide
    j = _read_json(PATH_SIGNALS_JSON, default=None)
    if isinstance(j, list):
        # déjà un tableau d’objets
        return j
    if isinstance(j, dict) and "items" in j and isinstance(j["items"], list):
        return j["items"]
    # fallback CSV
    return _signals_from_csv()

def _paginate(lst: List[Any], limit: int, offset: int):
    total = len(lst)
    if offset < 0: offset = 0
    if limit <= 0: limit = 200
    return total, lst[offset: offset + limit]

# ---------- endpoints ----------
@app.get("/viz/test")
def viz_test():
    return {"ok": True, "ver": APP_VER, "hints": {
        "produce_here": DATA_DIR, "reports_here": "/opt/scalp/reports"
    }}

@app.get("/api/signals_raw")
def api_signals_raw(limit: int = 200):
    items = _load_signals_raw()
    return items[:max(0, limit)]

@app.get("/api/signals")
def api_signals(
    sym: Optional[str] = Query(None, description="Ex: BTCUSDT,ETHUSDT"),
    tf: Optional[str]  = Query(None, description="Ex: 1m,5m,15m"),
    include_hold: bool = Query(False),
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
        items = [x for x in items if str(x.get("side","")).upper() != "HOLD"]
    # pagination
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
    if isinstance(j, dict) and "cells" in j:
        return j
    if isinstance(j, list):
        # parfois un simple tableau de cellules
        return {"cells": j, "source": "heatmap.json[list]"}
    # fallback: construire une heatmap plate depuis la watchlist
    syms = _read_watchlist()
    cells = [{"sym": s, "strength": 0.0} for s in syms]  # 0 = neutre
    return {"cells": cells, "source": "watchlist_fallback"}

@app.get("/viz/demo")
def viz_demo():
    # petite page pour voir rapidement les signaux (inclut HOLD)
    html = """
<!doctype html><meta charset="utf-8">
<title>SCALP • Demo</title>
<style>
 body{background:#0b0f17;color:#cdd6f4;font:14px/1.35 ui-sans-serif,system-ui}
 table{width:100%;border-collapse:collapse;margin-top:12px}
 th,td{padding:6px 8px;border-bottom:1px solid #1e2633;white-space:nowrap}
 th{position:sticky;top:0;background:#121826}
 .hold{color:#88a}
 .buy{color:#77f59b}
 .sell{color:#ff7b7b}
 #bar{display:flex;gap:10px;align-items:center}
 a,button{color:#7cc4ff}
 button{background:#1a2332;border:1px solid #283245;border-radius:6px;padding:6px 10px}
</style>
<div id="bar">
  <a href="/viz/hello">/viz/hello</a>
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
  document.getElementById('info').textContent =
    `total:${j.total||0} • loaded:${(j.items||[]).length}`;
}
load(); setInterval(load, 5000);
</script>
"""
    return HTMLResponse(html)

# compat
@app.get("/viz/hello")
def viz_hello(): return PlainTextResponse("hello")

# uvicorn si lancé à la main
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("viz_main:app", host="127.0.0.1", port=8100, reload=False)
