import os, time, asyncio, json, csv
from collections import defaultdict
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

VERSION = "rtviz-0.8"

DATA_DIR = "/opt/scalp/var/dashboard"
CSV_FILE = os.path.join(DATA_DIR, "signals.csv")
D_JSON = "/opt/scalp/data"
JSON_SIGNALS = os.path.join(D_JSON, "signals.json")   # (optionnel)
JSON_HISTORY = os.path.join(D_JSON, "history.json")
JSON_HEATMAP = os.path.join(D_JSON, "heatmap.json")

# ---------- helpers ----------
def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return default

def read_csv_tail(path, max_rows=5000):
    """Lit rapidement les dernières lignes (entier du fichier si petit)."""
    rows = []
    try:
        with open(path, newline="") as f:
            r = csv.DictReader(f)
            for row in r:
                rows.append(row)
    except Exception as e:
        return [], str(e)
    # garde la fin pour limiter la mémoire
    if len(rows) > max_rows:
        rows = rows[-max_rows:]
    return rows, None

# ---------- endpoints ----------
@app.get("/viz/test")
async def viz_test():
    return {"ok": True, "ver": VERSION}

@app.get("/viz/hello")
async def viz_hello():
    # petit “hint” que le front peut lire (si jamais)
    return {"ok": True, "ver": VERSION, "config": {"include_hold_default": True}}

@app.get("/api/signals_raw")
async def api_signals_raw(limit: int = 100):
    rows, err = read_csv_tail(CSV_FILE, max_rows=max(100, limit*20))
    if err:
        return {"error": err, "items": []}
    return rows[-limit:]

@app.get("/api/signals")
async def api_signals(
    limit: int = 100,
    include_hold: bool = True,   # <— par défaut maintenant
    sym: str | None = None,      # filtre éventuel (ex: BTCUSDT,ETHUSDT)
    tf: str | None = None        # filtre timeframe (ex: 1m,5m,15m)
):
    rows, err = read_csv_tail(CSV_FILE, max_rows=max(100, limit*40))
    if err:
        return {"error": err, "total": 0, "items": []}

    # filtres
    syms_filter = set()
    if sym:
        syms_filter = set([s.strip().upper() for s in sym.split(",") if s.strip()])

    out = []
    for row in rows:
        s = (row.get("signal") or "").upper()
        if not include_hold and s == "HOLD":
            continue
        if syms_filter and (row.get("symbol","").upper() not in syms_filter):
            continue
        if tf and row.get("tf","") != tf:
            continue
        try:
            ts = int(row.get("ts","0"))
        except:
            ts = 0
        out.append({
            "ts": ts,
            "sym": row.get("symbol",""),
            "tf": row.get("tf",""),
            "side": s,
            "score": 0,
            "entry": row.get("details",""),
            "details": row.get("details",""),
        })

    # on garde les plus récents
    out.sort(key=lambda x: x["ts"], reverse=True)
    out = out[:limit]
    return {"total": len(out), "items": out}

@app.get("/api/history")
async def api_history():
    return load_json(JSON_HISTORY, {"total": 0, "items": []})

@app.get("/viz/heatmap")
async def viz_heatmap():
    # 1) si un vrai heatmap.json est dispo et non vide -> renvoyer
    hmap = load_json(JSON_HEATMAP, {})
    if isinstance(hmap, dict) and hmap.get("cells"):
        return hmap

    # 2) fallback depuis le CSV (montre au moins une grille simple)
    rows, err = read_csv_tail(CSV_FILE, max_rows=3000)
    if err or not rows:
        return {"source": "fallback", "cells": []}

    # Construire une pseudo heatmap : agg par (symbol, tf), valeur 0..1 (HOLD=0)
    latest_by_key = {}
    for r in rows:
        key = (r.get("symbol",""), r.get("tf",""))
        latest_by_key[key] = r  # fin = plus récent

    cells = []
    for (sym, tf), r in latest_by_key.items():
        side = (r.get("signal") or "").upper()
        val = 0.0
        if side in ("BUY","LONG"): val = 1.0
        elif side in ("SELL","SHORT"): val = -1.0
        else: val = 0.0  # HOLD
        cells.append({"sym": sym, "tf": tf, "v": val})

    # tri pour stabilité d’affichage
    cells.sort(key=lambda c: (c["sym"], c["tf"]))
    return {"source": "signals.csv", "cells": cells}

@app.get("/viz/stream")
async def viz_stream(request: Request):
    async def eventgen():
        while True:
            if await request.is_disconnected():
                break
            yield f"data: ping {int(time.time())}\n\n"
            await asyncio.sleep(5)
    return StreamingResponse(eventgen(), media_type="text/event-stream")

# --- petite page de test rapide ---
@app.get("/viz/demo")
async def viz_demo():
    html = """
    <html><head><title>SCALP • Demo</title></head>
    <body style="background:#0b0f14;color:#e6edf3;font-family:ui-monospace,monospace">
      <h3>SCALP • Demo (auto-refresh 5s)</h3>
      <div id="out">loading…</div>
      <script>
      async function refresh(){
        let r = await fetch('/api/signals?include_hold=true&limit=15');
        let j = await r.json();
        document.getElementById('out').innerHTML =
          '<pre>'+JSON.stringify(j,null,2)+'</pre>';
      }
      setInterval(refresh, 5000); refresh();
      </script>
    </body></html>
    """
    return HTMLResponse(html)

if __name__ == "__main__":
    uvicorn.run("viz_main:app", host="127.0.0.1", port=8100, reload=False)
