#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, time, csv, socket
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# --- ENV ---
REPO_PATH = Path(os.environ.get("REPO_PATH", "/opt/scalp")).resolve()
DATA_DIR  = Path(os.environ.get("DATA_DIR", str(REPO_PATH / "var" / "dashboard"))).resolve()
HTML_PORT = int(os.environ.get("HTML_PORT", "5002"))   # <— on prend 5002
HEATMAP_WINDOW_MIN = int(os.environ.get("HEATMAP_WINDOW_MIN", "90"))
TFS = [t.strip() for t in os.environ.get("SCALP_TFS", "1m,5m,15m").split(",") if t.strip()]
SIGNALS_CSV = DATA_DIR / "signals.csv"

BUY, SELL, HOLD = "BUY", "SELL", "HOLD"

# --- IO robuste ---
def _read_signals():
    rows = []
    if not SIGNALS_CSV.exists():
        return rows
    try:
        with SIGNALS_CSV.open("r", encoding="utf-8", newline="") as f:
            rdr = csv.reader(f)
            for r in rdr:
                if not r: 
                    continue
                if r[0].lower() == "ts":  # ignore header éventuel
                    continue
                try:
                    ts = float(r[0])
                    if ts > 1e11:   # tolère timestamps en millisecondes
                        ts = ts / 1000.0
                    sym = r[1]
                    tf  = r[2]
                    sig = (r[3] or "").upper()
                    rows.append((ts, sym, tf, sig))
                except Exception:
                    continue
    except Exception:
        pass
    return rows

def _windowed_state(rows, window_min):
    cutoff = time.time() - window_min*60
    last_by, score_by, pairs = {}, {}, set()
    for ts, pair, tf, sig in rows:
        pairs.add(pair)
        key = (pair, tf)
        prev = last_by.get(key)
        if (prev is None) or (ts > prev[0]):
            last_by[key] = (ts, sig if sig in (BUY, SELL, HOLD) else HOLD)
        if ts >= cutoff:
            score_by[key] = score_by.get(key, 0) + (1 if sig==BUY else -1 if sig==SELL else 0)
    pairs = sorted(pairs)
    tfs = TFS[:]
    cells = []
    for p in pairs:
        for tf in tfs:
            last = last_by.get((p,tf), (0.0, HOLD))[1]
            score = score_by.get((p,tf), 0)
            cells.append({"pair": p, "tf": tf, "last": last, "score": int(score)})
    return {"pairs": pairs, "tfs": tfs, "cells": cells, "window_min": window_min}

# --- HTML minimal (AUCUN f-string) ---
HOST = socket.gethostname()
_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Scalp Dashboard</title>
<style>
 body{font-family:system-ui,Segoe UI,Roboto,Arial;margin:20px}
 pre{background:#111;color:#eee;padding:12px;border-radius:8px;overflow:auto}
</style>
</head>
<body>
<h1>Scalp Heatmap</h1>
<p>Host: HOST • Fenêtre par défaut: WIN min</p>
<p><a href="/api/state">/api/state</a></p>
<pre id="out">Chargement…</pre>
<script>
async function go(){
  try{
    const r = await fetch('/api/state');
    const s = await r.json();
    document.getElementById('out').textContent = JSON.stringify(s, null, 2);
  }catch(e){ document.getElementById('out').textContent = String(e); }
}
setInterval(go, 5000); go();
</script>
</body></html>
"""
_HTML = _HTML.replace("HOST", HOST).replace("WIN", str(HEATMAP_WINDOW_MIN))

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        if isinstance(body, str): body = body.encode("utf-8")
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path in ("/", "/index.html"):
            self._send(200, "text/html; charset=utf-8", _HTML); return
        if url.path == "/api/state":
            state = _windowed_state(_read_signals(), HEATMAP_WINDOW_MIN)
            self._send(200, "application/json; charset=utf-8", json.dumps(state)); return
        self._send(404, "text/plain; charset=utf-8", "Not Found")

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    httpd = ThreadingHTTPServer(("", HTML_PORT), Handler)
    print("dashboard on http://0.0.0.0:%d" % HTML_PORT)
    try: httpd.serve_forever()
    except KeyboardInterrupt: pass

if __name__ == "__main__":
    main()
