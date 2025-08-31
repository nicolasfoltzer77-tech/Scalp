#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Mini serveur HTTP autonome pour la Heatmap (pair × TF), sans ngrok ni Pages.
- GET /           -> HTML responsive (mobile-friendly) avec heatmap
- GET /api/state  -> JSON { pairs: [...], tfs: [...], cells: [{pair, tf, last, score}] }

Données d'entrée: var/dashboard/signals.csv (append-only)
Format attendu (produit par engine/utils/signal_sink.py):
  ts, symbol, tf, signal, details

ENV (tous optionnels):
  REPO_PATH=/opt/scalp
  DATA_DIR=$REPO_PATH/var/dashboard
  HTML_PORT=8888
  HEATMAP_WINDOW_MIN=90
  SCALP_TFS=1m,5m,15m
"""

from __future__ import annotations
import os, json, time, csv, socket
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta

# ---------- Configuration via ENV ----------
REPO_PATH = Path(os.environ.get("REPO_PATH", "/opt/scalp")).resolve()
DATA_DIR  = Path(os.environ.get("DATA_DIR", str(REPO_PATH / "var" / "dashboard"))).resolve()
HTML_PORT = int(os.environ.get("HTML_PORT", "8888"))

HEATMAP_WINDOW_MIN = int(os.environ.get("HEATMAP_WINDOW_MIN", "90"))
TFS = [t.strip() for t in os.environ.get("SCALP_TFS", "1m,5m,15m").split(",") if t.strip()]

SIGNALS_CSV = DATA_DIR / "signals.csv"

# ---------- Lecture & agrégation ----------
BUY, SELL, HOLD = "BUY", "SELL", "HOLD"

def _now_utc() -> float:
    return time.time()

def _read_signals():
    rows = []
    if not SIGNALS_CSV.exists():
        return rows
    try:
        with SIGNALS_CSV.open("r", encoding="utf-8", newline="") as f:
            rdr = csv.reader(f)
            header = next(rdr, None)
            # tolérant: cherche colonnes usuelles
            idx = {name: (header.index(name) if name in header else None) for name in ("ts","symbol","tf","signal","details")}
            if header is None or idx["ts"] is None or idx["symbol"] is None or idx["tf"] is None or idx["signal"] is None:
                # format inconnu -> on essaye positions standard
                f.seek(0)
                rdr = csv.reader(f)
                for r in rdr:
                    try:
                        ts, symbol, tf, signal = float(r[0]), r[1], r[2], r[3].upper()
                        rows.append((ts, symbol, tf, signal))
                    except Exception:
                        continue
                return rows
            for r in rdr:
                try:
                    ts = float(r[idx["ts"]])
                    symbol = r[idx["symbol"]]
                    tf = r[idx["tf"]]
                    signal = (r[idx["signal"]] or "").upper()
                    rows.append((ts, symbol, tf, signal))
                except Exception:
                    continue
    except Exception:
        # En cas de lecture concurrente partielle, on retourne ce qu'on a pu lire
        pass
    return rows

def _windowed_state(rows, window_min: int):
    """
    Calcule pour chaque (pair, tf):
      - last: dernier signal non vide (BUY/SELL/HOLD)
      - score: somme des signaux sur la fenêtre (BUY=+1, SELL=-1, HOLD=0)
    """
    cutoff = _now_utc() - window_min * 60
    last_by = {}   # (pair, tf) -> (ts, signal)
    score_by = {}  # (pair, tf) -> int
    pairs = set()
    for ts, pair, tf, sig in rows:
        pairs.add(pair)
        key = (pair, tf)
        # last
        prev = last_by.get(key)
        if prev is None or ts > prev[0]:
            last_by[key] = (ts, sig if sig in (BUY, SELL, HOLD) else HOLD)
        # within window -> score
        if ts >= cutoff:
            if sig == BUY:
                score_by[key] = score_by.get(key, 0) + 1
            elif sig == SELL:
                score_by[key] = score_by.get(key, 0) - 1
            else:
                score_by.setdefault(key, 0)

    # Normalise la grille (toutes combinaisons pair×tf présentes)
    pairs = sorted(pairs)
    tfs = TFS[:]  # colonnes configurées
    cells = []
    for pair in pairs:
        for tf in tfs:
            last = last_by.get((pair, tf), (0.0, HOLD))[1]
            score = score_by.get((pair, tf), 0)
            cells.append({"pair": pair, "tf": tf, "last": last, "score": int(score)})
    return {"pairs": pairs, "tfs": tfs, "cells": cells, "window_min": window_min}

# ---------- HTTP ----------
_HTML = f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Scalp • Heatmap (pair × TF)</title>
<style>
  :root {{
    --bg: #0f172a; --panel:#111827; --card:#1f2937; --text:#e5e7eb; --muted:#9ca3af;
    --buy:#16a34a; --sell:#dc2626; --hold:#374151;
  }}
  html,body{{margin:0;padding:0;background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,"Helvetica Neue",Arial}}
  .wrap{{max-width:1100px;margin:0 auto;padding:14px}}
  .toprow{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}}
  .badge{{background:#0b1220;border:1px solid #1f2937;border-radius:999px;padding:6px 10px;font-weight:600}}
  .status{{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:6px;background:#22c55e}}
  h1{{font-size:20px;margin:16px 0 8px}}
  .tbl{{width:100%;border-collapse:separate;border-spacing:0 8px}}
  .tbl th,.tbl td{{text-align:center;padding:8px 6px}}
  .tbl th{{font-size:12px;color:var(--muted)}}
  .row-head{{text-align:left;padding-left:10px;font-weight:700}}
  .pill{{display:inline-block;padding:6px 10px;border-radius:999px;font-weight:700;min-width:72px}}
  .buy{{background:rgba(22,163,74,.15);border:1px solid rgba(22,163,74,.5);color:#86efac}}
  .sell{{background:rgba(220,38,38,.15);border:1px solid rgba(220,38,38,.5);color:#fca5a5}}
  .hold{{background:rgba(55,65,81,.6);border:1px solid rgba(75,85,99,.8);color:#e5e7eb}}
  .score{{font-size:12px;color:var(--muted);margin-left:6px}}
  .foot{{margin-top:10px;color:var(--muted);font-size:12px}}
  .tabs{{margin-left:auto;display:flex;gap:6px}}
  .tab{{border:1px solid #374151;padding:4px 10px;border-radius:8px;color:#cbd5e1;text-decoration:none}}
</style>
</head>
<body>
<div class="wrap">
  <div class="toprow">
    <span class="badge"><span class="status"></span>Online</span>
    <span class="badge">Heatmap</span>
    <span class="badge">Fenêtre: <span id="win">-</span> min</span>
    <div class="tabs">
      <a class="tab" href="#" onclick="setWin(30);return false;">30m</a>
      <a class="tab" href="#" onclick="setWin(60);return false;">1h</a>
      <a class="tab" href="#" onclick="setWin(120);return false;">2h</a>
    </div>
  </div>

  <h1>Heatmap (pair × TF)</h1>
  <p style="color:#9ca3af;font-size:13px;margin-top:0">
    Pastilles BUY/SELL/HOLD + score (activité &amp; direction : BUY=+1, SELL=-1, HOLD=0, somme des sous-strat. sur la fenêtre).
  </p>
  <table class="tbl" id="grid"></table>
  <div class="foot">Host: {socket.gethostname()} • Heure locale: <span id="clock"></span></div>
</div>

<script>
let WINDOW_MIN = {HEATMAP_WINDOW_MIN};

function setWin(m){ WINDOW_MIN = m; localStorage.setItem('heatmap_window', m); render(); }
function cls(sig){ sig=(sig||'HOLD').toUpperCase(); if(sig==='BUY') return 'pill buy'; if(sig==='SELL') return 'pill sell'; return 'pill hold'; }
function txt(sig){ sig=(sig||'HOLD').toUpperCase(); return sig; }

async function fetchState(){
  const r = await fetch('/api/state?window=' + WINDOW_MIN + '&_=' + Date.now());
  if(!r.ok) throw new Error('HTTP '+r.status);
  return await r.json();
}

function buildGrid(state){
  const t = document.getElementById('grid');
  const pairs = state.pairs || [];
  const tfs = state.tfs || [];
  const cells = state.cells || [];
  const head = document.createElement('thead');
  const trh = document.createElement('tr');
  trh.appendChild(cell('th','Pair\\TF','row-head'));
  tfs.forEach(tf=> trh.appendChild(cell('th', tf)));
  head.appendChild(trh);

  const body = document.createElement('tbody');
  pairs.forEach(p => {
    const tr = document.createElement('tr');
    tr.appendChild(cell('td', p, 'row-head'));
    tfs.forEach(tf => {
      const c = cells.find(x => x.pair===p && x.tf===tf) || {last:'HOLD', score:0};
      const d = document.createElement('td');
      const span = document.createElement('span');
      span.className = cls(c.last);
      span.textContent = txt(c.last);
      const sc = document.createElement('span');
      sc.className = 'score';
      sc.textContent = c.score;
      d.appendChild(span); d.appendChild(sc);
      tr.appendChild(d);
    });
    body.appendChild(tr);
  });

  t.innerHTML = '';
  t.appendChild(head);
  t.appendChild(body);
  document.getElementById('win').textContent = state.window_min;
}

function cell(tag, text, cls){ const el = document.createElement(tag); el.textContent = text; if(cls) el.className = cls; return el; }

async function render(){
  try{
    const s = await fetchState();
    buildGrid(s);
  }catch(e){
    console.error(e);
  }
}
function tick(){
  document.getElementById('clock').textContent = new Date().toLocaleString();
}
setInterval(render, 10_000);
setInterval(tick, 1_000);
tick();
WINDOW_MIN = parseInt(localStorage.getItem('heatmap_window') || WINDOW_MIN, 10);
render();
</script>
</body>
</html>
"""

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, ctype, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/" or url.path == "/index.html":
            self._send(200, "text/html; charset=utf-8", _HTML.encode("utf-8"))
            return
        if url.path == "/api/state":
            try:
                qs = dict([p.split("=") for p in (url.query or "").split("&") if "=" in p])
            except Exception:
                qs = {}
            try:
                window = int(qs.get("window") or HEATMAP_WINDOW_MIN)
            except Exception:
                window = HEATMAP_WINDOW_MIN
            rows = _read_signals()
            state = _windowed_state(rows, window)
            body = json.dumps(state, ensure_ascii=False).encode("utf-8")
            self._send(200, "application/json; charset=utf-8", body)
            return
        self._send(404, "text/plain; charset=utf-8", b"Not Found")

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    httpd = ThreadingHTTPServer(("", HTML_PORT), Handler)
    print(f"[dashboard] Serving on http://0.0.0.0:{HTML_PORT}  (DATA_DIR={DATA_DIR})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
