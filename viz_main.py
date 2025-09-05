# -*- coding: utf-8 -*-
"""
SCALP - RealTime Viz API
FastAPI app exposant :
- /viz/test, /viz/hello
- /api/signals_raw (array)
- /api/signals      (paginated object)
- /api/history
- /viz/heatmap      (json or fallback depuis CSV)
- /viz/stream       (SSE ping + nouveaux signaux)
- /viz/demo         (page HTML de test)

Aucun package exotique requis (csv, json, FastAPI/Starlette uniquement).
"""

from __future__ import annotations
import os
import io
import csv
import json
import time
import asyncio
from collections import deque, defaultdict
from typing import Dict, List, Optional, Iterable, Tuple

from fastapi import FastAPI, Request, Query
from fastapi.responses import JSONResponse, HTMLResponse, PlainTextResponse, StreamingResponse

RTVIZ_VER = "rtviz-0.8"

app = FastAPI(title="SCALP – Visualisation", version=RTVIZ_VER)


# ---------- Utilitaires de chemins ----------

def _first_existing(paths: Iterable[str]) -> Optional[str]:
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None

def resolve_paths() -> Dict[str, Optional[str]]:
    data_dir = "/opt/scalp/data"
    var_dash = "/opt/scalp/var/dashboard"

    return {
        "signals_csv": _first_existing([
            os.environ.get("SCALP_SIGNALS_CSV"),
            os.path.join(var_dash, "signals.csv"),
        ]),
        "signals_json": _first_existing([
            os.path.join(data_dir, "signals.json"),
        ]),
        "history_json": _first_existing([
            os.path.join(data_dir, "history.json"),
        ]),
        "heatmap_json": _first_existing([
            os.path.join(data_dir, "heatmap.json"),
        ]),
        "watchlist_yaml": _first_existing([
            os.path.join("/opt/scalp/reports", "watchlist.yml"),
            os.path.join("/opt/scalp/reports", "watchlist.yaml"),
        ]),
    }


# ---------- Lecture JSON/CSV ----------

def load_json(path: Optional[str]) -> Optional[object]:
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _tail_lines(path: str, max_lines: int = 5000) -> List[str]:
    """Lit rapidement les N dernières lignes d'un gros fichier."""
    if not os.path.exists(path):
        return []
    size = os.path.getsize(path)
    # Sécurité: si fichier < 3 Mo, lis tout d'un coup
    block = 1024 * 64
    data = bytearray()
    with open(path, "rb") as f:
        pos = max(0, size - block)
        f.seek(pos)
        data.extend(f.read())
        # élargir si pas assez de lignes
        while data.count(b"\n") < max_lines and pos > 0:
            pos = max(0, pos - block)
            f.seek(pos)
            chunk = f.read(min(block, len(data)))
            data = bytearray(chunk) + data
            if pos == 0:
                break
    text = data.decode("utf-8", errors="ignore")
    lines = text.strip().splitlines()
    return lines[-max_lines:]


def parse_signals_csv_lines(lines: List[str]) -> List[Dict]:
    """CSV attendu: ts,symbol,tf,signal,details"""
    if not lines:
        return []
    # s'assurer qu'on a un en-tête
    if not lines[0].lower().startswith("ts,"):
        # tenter d'ajouter un header si absent
        lines = ["ts,symbol,tf,signal,details"] + lines
    buff = io.StringIO("\n".join(lines))
    rdr = csv.DictReader(buff)
    items = []
    for r in rdr:
        if not r:
            continue
        try:
            ts_raw = r.get("ts") or r.get("timestamp")
            ts_int = int(float(ts_raw)) if ts_raw else 0
        except Exception:
            ts_int = 0
        sym = (r.get("symbol") or r.get("sym") or "").strip()
        tf = (r.get("tf") or r.get("timeframe") or "").strip()
        side = (r.get("signal") or r.get("side") or "").strip().upper() or "HOLD"
        details = (r.get("details") or r.get("entry") or "").strip()
        item = {
            "ts": ts_int,
            "sym": sym,
            "tf": tf,
            "side": side,
            "score": 0 if side == "HOLD" else (1 if side == "BUY" else -1),
            "entry": details or "",
            "details": details or "",
        }
        # filtrer lignes vides
        if item["sym"]:
            items.append(item)
    # tri récents d'abord
    items.sort(key=lambda x: x["ts"], reverse=True)
    return items


def load_signals_any(limit_scan: int = 5000) -> List[Dict]:
    """Charge depuis CSV si présent, sinon depuis signals.json (items ou array brut)."""
    p = resolve_paths()
    # priorité CSV
    if p["signals_csv"]:
        lines = _tail_lines(p["signals_csv"], max_lines=limit_scan)
        return parse_signals_csv_lines(lines)

    # fallback JSON
    js = load_json(p["signals_json"])
    if isinstance(js, dict) and "items" in js:
        items = js.get("items") or []
    elif isinstance(js, list):
        items = js
    else:
        items = []
    # normalise
    norm = []
    for r in items:
        side = (r.get("side") or r.get("signal") or "HOLD").upper()
        norm.append({
            "ts": int(r.get("ts", 0)),
            "sym": r.get("sym") or r.get("symbol") or "",
            "tf": r.get("tf") or "",
            "side": side,
            "score": 0 if side == "HOLD" else (1 if side == "BUY" else -1),
            "entry": r.get("entry") or r.get("details") or "",
            "details": r.get("details") or r.get("entry") or "",
        })
    norm.sort(key=lambda x: x["ts"], reverse=True)
    return norm


# ---------- Endpoints de base ----------

@app.get("/viz/test")
def viz_test():
    return {"ok": True, "ver": RTVIZ_VER}

@app.get("/viz/hello")
def viz_hello():
    return PlainTextResponse("hello from rtviz", media_type="text/plain")


# ---------- API SIGNALS ----------

def _apply_filters(items: List[Dict],
                   sym: Optional[str],
                   tf: Optional[str],
                   include_hold: bool) -> List[Dict]:
    syms = set([s.strip().upper() for s in sym.split(",")]) if sym else None
    tfs = set([t.strip() for t in tf.split(",")]) if tf else None

    out = []
    for it in items:
        if not include_hold and it["side"] == "HOLD":
            continue
        if syms and it["sym"].upper() not in syms:
            continue
        if tfs and it["tf"] not in tfs:
            continue
        out.append(it)
    return out


@app.get("/api/signals_raw")
def api_signals_raw(limit: int = Query(100, ge=1, le=2000),
                    sym: Optional[str] = None,
                    tf: Optional[str] = None,
                    include_hold: bool = False):
    items = load_signals_any(limit_scan=5000)
    items = _apply_filters(items, sym, tf, include_hold)
    return items[:limit]


@app.get("/api/signals")
def api_signals(limit: int = Query(100, ge=1, le=500),
                offset: int = Query(0, ge=0),
                sym: Optional[str] = None,
                tf: Optional[str] = None,
                include_hold: bool = False):
    items = load_signals_any(limit_scan=6000)
    items = _apply_filters(items, sym, tf, include_hold)
    total = len(items)
    slice_ = items[offset:offset+limit]
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": slice_
    }


# ---------- API HISTORY ----------

@app.get("/api/history")
def api_history(limit: int = Query(100, ge=1, le=1000),
                offset: int = Query(0, ge=0)):
    p = resolve_paths()
    js = load_json(p["history_json"]) or {}
    # formats acceptés : {items: [...]} ou [...]
    items = js.get("items") if isinstance(js, dict) else (js if isinstance(js, list) else [])
    if not isinstance(items, list):
        items = []
    # normalisation légère
    for it in items:
        if "sym" not in it and "symbol" in it:
            it["sym"] = it.get("symbol")
    total = len(items)
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items[offset:offset+limit]
    }


# ---------- VIZ HEATMAP ----------

def _build_heatmap_from_signals(items: List[Dict], max_per_sym: int = 3) -> Dict:
    """
    Construit une heatmap simple :
      v = intensité Buy ∈ {0, 1}, 1 si BUY, 0 sinon (HOLD/SELL)
    On garde jusqu'à 3 TF récentes par symbole.
    """
    # groupement par (sym, tf) en gardant la + récente
    latest: Dict[Tuple[str, str], Dict] = {}
    for it in items:
        key = (it["sym"], it["tf"])
        if key not in latest or it["ts"] > latest[key]["ts"]:
            latest[key] = it

    # pour chaque symbole, ne garder que les max_per_sym plus récents
    by_sym: Dict[str, List[Dict]] = defaultdict(list)
    for (sym, tf), it in latest.items():
        by_sym[sym].append(it)
    cells = []
    for sym, arr in by_sym.items():
        arr.sort(key=lambda x: x["ts"], reverse=True)
        for it in arr[:max_per_sym]:
            v = 1.0 if it["side"] == "BUY" else 0.0
            cells.append({"sym": sym, "tf": it["tf"], "side": it["side"], "v": v})
    # tri visuel par symbole
    cells.sort(key=lambda c: (c["sym"], c["tf"]))
    return {"source": "signals.csv", "cells": cells}

@app.get("/viz/heatmap")
def viz_heatmap():
    p = resolve_paths()
    # tenter heatmap.json si présent
    js = load_json(p["heatmap_json"])
    if isinstance(js, dict) and "cells" in js:
        return js
    # fallback dynamique depuis CSV
    items = load_signals_any(limit_scan=5000)
    return _build_heatmap_from_signals(items)


# ---------- SSE STREAM ----------

def _format_sse(data: str, event: Optional[str] = None, id_: Optional[str] = None) -> str:
    out = []
    if event:
        out.append(f"event: {event}")
    if id_:
        out.append(f"id: {id_}")
    # data peut contenir des retours ligne → préfixer chaque ligne par "data: "
    for line in data.splitlines() or [""]:
        out.append(f"data: {line}")
    out.append("")  # ligne vide de terminaison
    return "\n".join(out)

async def _sse_generator(request: Request):
    """
    Stream :
      - message d'info de départ (counts fichiers)
      - ping toutes 5s
      - nouveaux enregistrements append dans signals.csv
    """
    p = resolve_paths()
    # message d'info
    counts = {
        "signals.csv": os.path.getsize(p["signals_csv"]) if p["signals_csv"] and os.path.exists(p["signals_csv"]) else None,
        "signals.json": (len((load_json(p["signals_json"]) or {}).get("items", []))
                         if p["signals_json"] else None),
        "history.json": (len((load_json(p["history_json"]) or {}).get("items", []))
                         if p["history_json"] else None),
        "heatmap.json": (len((load_json(p["heatmap_json"]) or {}).get("cells", []))
                         if p["heatmap_json"] else None),
    }
    yield _format_sse(json.dumps({"ver": RTVIZ_VER, "counts": counts}), event="info")

    # pointer au bout du fichier CSV pour ne pousser que du neuf
    f = None
    pos = 0
    if p["signals_csv"] and os.path.exists(p["signals_csv"]):
        f = open(p["signals_csv"], "r", encoding="utf-8", errors="ignore")
        f.seek(0, os.SEEK_END)
        pos = f.tell()

    last_ping = time.time()
    eid = 0

    try:
        while True:
            if await request.is_disconnected():
                break

            pushed = False
            if f:
                line = f.readline()
                if not line:
                    # rien de neuf
                    await asyncio.sleep(0.5)
                else:
                    # nouvelle ligne → parser et pousser
                    items = parse_signals_csv_lines([line])
                    if items:
                        eid += 1
                        yield _format_sse(json.dumps(items[0]), event="signal", id_=str(eid))
                        pushed = True

            # ping toutes 5s pour garder la connexion vivante
            now = time.time()
            if not pushed and (now - last_ping) >= 5.0:
                eid += 1
                yield _format_sse(json.dumps({"ping": int(now)}), event="ping", id_=str(eid))
                last_ping = now
    finally:
        if f:
            f.close()

@app.get("/viz/stream")
async def viz_stream(request: Request):
    headers = {"Content-Type": "text/event-stream", "Cache-Control": "no-cache", "Connection": "keep-alive"}
    return StreamingResponse(_sse_generator(request), headers=headers, media_type="text/event-stream")


# ---------- DEMO HTML (debug simple) ----------

@app.get("/viz/demo")
def viz_demo():
    html = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"/>
<title>SCALP • Demo</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
 body{{background:#0f141b;color:#d7e1ec;font-family:system-ui,Segoe UI,Roboto,Arial,sans-serif}}
 a,button{{color:#9ad0ff}}
 table{{width:100%;border-collapse:collapse;margin-top:12px}}
 th,td{{padding:6px 8px;border-bottom:1px solid #223}}
 th{{text-align:left;color:#9ab}}
 .muted{{color:#778}}
 .tag{{padding:2px 6px;border-radius:6px;background:#1b2430;color:#b7c6d9;border:1px solid #2a394a}}
</style>
</head><body>
<h3>SCALP • Demo <small class="muted">(auto-refresh 5s)</small></h3>
<div>
  <a href="/viz/hello">/viz/hello</a> ·
  <a href="/api/signals">/api/signals</a>
  <button id="refresh">⟳ Refresh</button>
</div>
<table id="tbl"><thead>
<tr><th>ts (UTC)</th><th>sym</th><th>tf</th><th>side</th><th>entry/details</th></tr>
</thead><tbody></tbody></table>
<script>
const fmtTs = (t)=> {
  try{{let d=new Date(parseInt(t,10)*1000); return d.toISOString().replace('T',' ').replace('.000Z','');}}
  catch(e){{return t}}
};
async function load(){{
  let r = await fetch('/api/signals?include_hold=true&limit=100');
  let js = await r.json();
  let rows = js.items||[];
  let tb = document.querySelector('#tbl tbody');
  tb.innerHTML='';
  for (let it of rows){{
    let tr=document.createElement('tr');
    tr.innerHTML=`<td class="muted">${{fmtTs(it.ts)}}</td>
                  <td><span class="tag">${{it.sym}}</span></td>
                  <td class="muted">${{it.tf}}</td>
                  <td>${{it.side}}</td>
                  <td class="muted">${{it.entry||it.details||''}}</td>`;
    tb.appendChild(tr);
  }}
}}
document.querySelector('#refresh').onclick=load;
load();
setInterval(load, 5000);

// SSE
try {{
  const es = new EventSource('/viz/stream');
  es.onmessage = (ev)=>{{ /* pings */ }};
  es.addEventListener('signal', ev => {{
    // prépend la dernière ligne en tête
    let it = JSON.parse(ev.data);
    let tb = document.querySelector('#tbl tbody');
    let tr=document.createElement('tr');
    tr.innerHTML=`<td class="muted">${{fmtTs(it.ts)}}</td>
                  <td><span class="tag">${{it.sym}}</span></td>
                  <td class="muted">${{it.tf}}</td>
                  <td>${{it.side}}</td>
                  <td class="muted">${{it.entry||it.details||''}}</td>`;
    tb.prepend(tr);
  }});
}} catch(e){{ console.log('SSE off', e); }}
</script>
</body></html>"""
    return HTMLResponse(html)


# ---------- Lancement local ----------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("viz_main:app", host="127.0.0.1", port=8100, log_level="info")
