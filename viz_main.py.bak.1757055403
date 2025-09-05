import os, re, time, asyncio, json, csv
from collections import defaultdict
from typing import Tuple, List
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# yaml est optionnel : si absent, on fera un parse "best effort"
try:
    import yaml  # type: ignore
except Exception:
    yaml = None  # fallback

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

VERSION = "rtviz-0.9"

DATA_DIR = "/opt/scalp/var/dashboard"
CSV_FILE = os.path.join(DATA_DIR, "signals.csv")

D_JSON = "/opt/scalp/data"
JSON_SIGNALS = os.path.join(D_JSON, "signals.json")
JSON_HISTORY = os.path.join(D_JSON, "history.json")
JSON_HEATMAP = os.path.join(D_JSON, "heatmap.json")

WATCHLIST_YAML = "/opt/scalp/reports/watchlist.yml"
WATCHLIST_YAML_ALT = "/opt/scalp/reports/watchlist.yaml"

# ---------- helpers ----------
def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return default

def read_csv_tail(path, max_rows=5000):
    rows = []
    try:
        with open(path, newline="") as f:
            r = csv.DictReader(f)
            for row in r:
                rows.append(row)
    except Exception as e:
        return [], str(e)
    if len(rows) > max_rows:
        rows = rows[-max_rows:]
    return rows, None

def parse_watchlist() -> Tuple[List[str], List[str]]:
    """
    Essaie d'extraire (symbols, timeframes) depuis watchlist.yml / .yaml.
    Supporte :
      symbols: [BTCUSDT, ETHUSDT]
      timeframes: [1m,5m,15m]
    Si yaml n'est pas dispo: parse "best effort" des lignes.
    """
    path = WATCHLIST_YAML if os.path.exists(WATCHLIST_YAML) else WATCHLIST_YAML_ALT
    if not os.path.exists(path):
        return [], []

    try:
        if yaml:
            with open(path) as f:
                doc = yaml.safe_load(f) or {}
            syms = doc.get("symbols") or doc.get("watchlist") or []
            if isinstance(syms, dict):
                # parfois {symbols: {binance: [..]}}
                syms = syms.get("binance") or syms.get("default") or []
            if not isinstance(syms, list):
                syms = []
            tfs = doc.get("timeframes") or ["1m","5m","15m"]
            if not isinstance(tfs, list):
                tfs = ["1m","5m","15m"]
            syms = [str(s).upper() for s in syms]
            tfs  = [str(t) for t in tfs]
            return syms, tfs
        else:
            # parse texto
            txt = open(path).read()
            syms = re.findall(r'\b[A-Z0-9]{3,}USDT\b', txt)
            tfs  = re.findall(r'\b(1m|3m|5m|15m|30m|1h|4h|1d)\b', txt)
            if not tfs:
                tfs = ["1m","5m","15m"]
            return sorted(set(syms)), sorted(set(tfs), key=lambda x: ["1m","3m","5m","15m","30m","1h","4h","1d"].index(x) if x in ["1m","3m","5m","15m","30m","1h","4h","1d"] else 99)
    except:
        return [], []

# ---------- endpoints ----------
@app.get("/viz/test")
async def viz_test():
    # quelques stats rapides pour debug
    sizes = {}
    for p in [CSV_FILE, JSON_SIGNALS, JSON_HISTORY, JSON_HEATMAP]:
        try:
            sizes[os.path.basename(p)] = os.path.getsize(p)
        except:
            pass
    return {"ok": True, "ver": VERSION, **sizes}

@app.get("/viz/hello")
async def viz_hello():
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
    include_hold: bool = True,
    sym: str | None = None,
    tf: str | None = None
):
    rows, err = read_csv_tail(CSV_FILE, max_rows=max(100, limit*40))
    if err:
        return {"error": err, "total": 0, "items": []}

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

    out.sort(key=lambda x: x["ts"], reverse=True)
    out = out[:limit]
    return {"total": len(out), "items": out}

@app.get("/api/history")
async def api_history():
    return load_json(JSON_HISTORY, {"total": 0, "items": []})

@app.get("/viz/heatmap")
async def viz_heatmap():
    # 1) heatmap.json fourni
    hmap = load_json(JSON_HEATMAP, {})
    if isinstance(hmap, dict) and hmap.get("cells"):
        hmap.setdefault("source", "heatmap.json")
        return hmap

    # 2) construire depuis CSV si dispo
    rows, err = read_csv_tail(CSV_FILE, max_rows=3000)
    if not err and rows:
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
            else: val = 0.0
            cells.append({"sym": sym, "tf": tf, "v": val})
        cells.sort(key=lambda c: (c["sym"], c["tf"]))
        return {"source": "signals.csv", "cells": cells}

    # 3) fallback WATCHLIST -> grille neutre (v=0) mais visible
    syms, tfs = parse_watchlist()
    if syms and tfs:
        cells = [{"sym": s, "tf": t, "v": 0.0} for s in syms for t in tfs]
        cells.sort(key=lambda c: (c["sym"], c["tf"]))
        return {"source": "watchlist.yml", "cells": cells}

    # 4) nada
    return {"source": "empty", "cells": []}

@app.get("/viz/stream")
async def viz_stream(request: Request):
    async def eventgen():
        while True:
            if await request.is_disconnected():
                break
            yield f"data: ping {int(time.time())}\n\n"
            await asyncio.sleep(5)
    return StreamingResponse(eventgen(), media_type="text/event-stream")

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
