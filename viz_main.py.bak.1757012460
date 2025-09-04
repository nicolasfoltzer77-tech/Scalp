#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Optional, List, Dict, Any, Set
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, HTMLResponse, PlainTextResponse

# >>> on garde l’adapter existant
from webviz.realtimeviz.adapter import (
    get_signals_snapshot,
    get_history_snapshot,
    get_heatmap_snapshot,
    sources_info,
)

app = FastAPI(title="SCALP rtviz")

# ---- helpers ---------------------------------------------------------------

def _split_opts(value: Optional[str]) -> Optional[Set[str]]:
    """'a,b,c' -> {'a','b','c'} ; None/'' -> None ; trim + upper pour sym, lower pour tf/side gérés en appelant."""
    if not value:
        return None
    return {tok.strip() for tok in value.split(",") if tok.strip()}

def _normalize_item(o: Dict[str, Any]) -> Dict[str, Any]:
    """
    L’adapter peut renvoyer soit {"items":[...]} soit la liste.
    Ici on normalise le format d’un item (ts,sym,tf,side,score,entry,details).
    """
    # alias possibles selon versions
    sym = o.get("sym") or o.get("symbol")
    tf = o.get("tf") or o.get("timeframe") or o.get("tfm")
    side = o.get("side") or o.get("signal")
    return {
        "ts": o.get("ts") or o.get("timestamp"),
        "sym": sym,
        "tf": tf,
        "side": side,
        "score": o.get("score", 0),
        "entry": o.get("entry") or o.get("details"),
        "details": o.get("details") or o.get("entry"),
    }

def _materialize_items(snapshot: Any) -> List[Dict[str, Any]]:
    """Accepte dict {'items': [...]} ou liste brute."""
    if isinstance(snapshot, dict):
        items = snapshot.get("items", [])
    else:
        items = snapshot or []
    return [_normalize_item(x) for x in items]

# ---- endpoints API ---------------------------------------------------------

@app.get("/viz/test")
def viz_test():
    return {"ok": True, "ver": "rtviz-0.5"}

@app.get("/viz/hello", response_class=PlainTextResponse)
def viz_hello():
    return "hello from rtviz"

@app.get("/api/heatmap")
def api_heatmap():
    return get_heatmap_snapshot()

@app.get("/api/history")
def api_history(limit: int = Query(1000, ge=1, le=5000)):
    snap = get_history_snapshot(limit=limit)
    return snap if isinstance(snap, dict) else {"items": snap}

@app.get("/api/signals_raw")
def api_signals_raw(
    include_hold: bool = Query(True),
    limit: int = Query(200, ge=1, le=5000),
):
    """Liste brute (array) — utile pour /viz/demo."""
    snap = get_signals_snapshot(limit=limit, include_hold=include_hold)
    items = _materialize_items(snap)
    return items

@app.get("/api/signals")
def api_signals(
    sym: Optional[str] = Query(None, description="ex: BTCUSDT,ETHUSDT"),
    tf: Optional[str] = Query(None, description="ex: 1m,5m,15m"),
    side: Optional[str] = Query(None, description="HOLD|BUY|SELL"),
    include_hold: bool = Query(True, description="inclure les HOLD"),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
):
    """
    Snapshot avec filtres + pagination.
    Renvoie: {"items":[...], "total":N, "limit":..., "offset":...}
    """
    snap = get_signals_snapshot(limit=5000, include_hold=include_hold)
    items = _materialize_items(snap)

    # Prépare filtres
    sym_set = {s.upper() for s in _split_opts(sym) or []}
    tf_set  = {t.lower() for t in _split_opts(tf)  or []}
    side_set= {s.upper() for s in _split_opts(side) or []}

    def keep(x: Dict[str, Any]) -> bool:
        if sym_set and (x.get("sym") or "").upper() not in sym_set:
            return False
        if tf_set and (x.get("tf") or "").lower() not in tf_set:
            return False
        if side_set and (x.get("side") or "").upper() not in side_set:
            return False
        if not include_hold and (x.get("side") or "").upper() == "HOLD":
            return False
        return True

    filtered = [x for x in items if keep(x)]
    total = len(filtered)

    # pagination
    start = offset
    end = min(offset + limit, total)
    page = filtered[start:end]

    return {"items": page, "total": total, "limit": limit, "offset": offset}

# ---- mini vue /viz/demo ----------------------------------------------------

@app.get("/viz/demo", response_class=HTMLResponse)
def viz_demo():
    html = """
<!doctype html><html><head><meta charset="utf-8">
<title>SCALP • Demo</title>
<style>
body{background:#0b0f14;color:#e8eef5;font:14px/1.4 system-ui,Segoe UI,Roboto}
table{border-collapse:collapse;width:100%}
th,td{padding:.45rem .6rem;border-bottom:1px solid #223}
thead th{position:sticky;top:0;background:#111a22}
.badge{display:inline-block;padding:.1rem .35rem;border-radius:.35rem;background:#173;color:#9f9}
.controls{display:flex;gap:.5rem;margin:.6rem 0}
input,select,button{background:#0e1620;color:#e8eef5;border:1px solid #223;border-radius:.4rem;padding:.35rem .5rem}
button{cursor:pointer}
</style>
</head><body>
<h3>SCALP • Demo (auto-refresh 5s)</h3>
<div class="controls">
  <input id="sym" placeholder="sym: BTCUSDT,ETHUSDT"/>
  <input id="tf" placeholder="tf: 1m,5m,15m"/>
  <select id="side">
    <option value="">side: any</option>
    <option>HOLD</option><option>BUY</option><option>SELL</option>
  </select>
  <label><input type="checkbox" id="hold" checked> include HOLD</label>
  <button id="refresh">Refresh</button>
</div>
<table id="t">
  <thead><tr><th>ts (UTC)</th><th>sym</th><th>tf</th><th>side</th><th>score</th><th>entry/details</th></tr></thead>
  <tbody></tbody>
</table>
<script>
async function load() {
  const params = new URLSearchParams();
  const sym = document.getElementById('sym').value.trim();
  const tf  = document.getElementById('tf').value.trim();
  const side= document.getElementById('side').value.trim();
  const hold= document.getElementById('hold').checked;
  if (sym) params.set('sym', sym);
  if (tf)  params.set('tf', tf);
  if (side)params.set('side', side);
  params.set('include_hold', hold ? 'true':'false');
  params.set('limit','200');
  const r = await fetch('/api/signals?'+params.toString());
  if (!r.ok) { console.error('api/signals failed'); return; }
  const data = await r.json();
  const rows = (data.items||[]);
  const tb = document.querySelector('#t tbody');
  tb.innerHTML = rows.map(x => `
    <tr>
      <td>${x.ts||''}</td>
      <td>${x.sym||''}</td>
      <td>${x.tf||''}</td>
      <td><span class="badge">${(x.side||'').toUpperCase()}</span></td>
      <td>${x.score??''}</td>
      <td>${x.entry||x.details||''}</td>
    </tr>`).join('');
}
document.getElementById('refresh').onclick = load;
setInterval(load, 5000);
load();
</script>
</body></html>
    """.strip()
    return HTMLResponse(content=html)

# ---- main (dev) ------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8100, proxy_headers=True, log_level="info")
