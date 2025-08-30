#!/usr/bin/env python3
from __future__ import annotations
import csv, os, time
from collections import defaultdict, deque
from typing import Dict, List, Tuple

CSV = "/opt/scalp/var/dashboard/signals.csv"
OUT = "/opt/scalp/dashboard.html"
NOW = int(time.time())

def load_rows(path: str) -> List[Dict[str, str]]:
    if not os.path.exists(path): return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def build_heatmap(rows: List[Dict[str, str]]):
    last: Dict[Tuple[str,str], Tuple[str,int]] = {}
    for r in rows:
        try:
            ts = int(r.get("ts", "0"))
            sym = r.get("symbol","")
            tf  = r.get("tf","")
            sig = (r.get("signal") or "HOLD").upper()
            if sym and tf:
                last[(sym, tf)] = (sig, ts)
        except Exception:
            pass
    symbols = sorted({s for (s, _) in last.keys()})
    tfs = sorted({t for (_, t) in last.keys()}, key=lambda x: (len(x), x))
    matrix, counts = [], defaultdict(int)
    for s in symbols:
        line: List[str] = []
        for tf in tfs:
            sig, ts = last.get((s, tf), ("MIS", 0))
            if ts == 0 or sig not in ("BUY","SELL","HOLD"): sig = "MIS" if ts == 0 else "HOLD"
            line.append(sig); counts[sig]+=1
        matrix.append((s, line))
    return symbols, tfs, matrix, counts

def top_signals(rows: List[Dict[str,str]], n: int = 25):
    dq = deque()
    for r in rows:
        try:
            r["ts"] = int(r.get("ts","0"))
            r["signal"] = (r.get("signal") or "HOLD").upper()
            dq.append(r)
        except Exception:
            pass
    out = list(dq)[-n:]; out.reverse()
    return out

def render(symbols, tfs, matrix, counts, latest) -> str:
    def cell(sig: str) -> str:
        colors = {"BUY":"#16a34a","SELL":"#dc2626","HOLD":"#64748b","MIS":"#9ca3af"}
        return f'<td style="background:{colors.get(sig,"#9ca3af")};color:#fff;text-align:center;padding:6px">{sig}</td>'
    html = []
    html.append(f"""<!doctype html>
<html><head><meta charset="utf-8"><title>SCALP — Dashboard</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<script>const SEC=5;addEventListener('DOMContentLoaded',()=>setInterval(()=>location.reload(),SEC*1000));</script>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Inter,Helvetica,Arial,sans-serif;margin:24px;color:#111827}}
.card{{border:1px solid #e5e7eb;border-radius:12px;padding:16px;margin:16px 0}}
.badge{{display:inline-block;padding:6px 10px;border-radius:999px;color:#fff;margin-right:8px;font-weight:600}}
.badge.gray{{background:#6b7280}} .badge.green{{background:#16a34a}}
table{{border-collapse:separate;border-spacing:6px}} thead th{{font-size:12px;color:#374151}}
.small{{font-size:12px;color:#6b7280}}
</style></head><body>
<h1>SCALP — Dashboard <span class="small">({time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(NOW))})</span></h1>
<div class="card">
  <h3>Compteurs</h3>
  <span class="badge gray">MIS: {counts.get("MIS",0)}</span>
  <span class="badge green">OK: {counts.get("BUY",0)+counts.get("SELL",0)+counts.get("HOLD",0)}</span>
  <div class="small">OK = dernière valeur BUY/SELL/HOLD • MIS = aucune donnée</div>
</div>
<div class="card"><h3>Heatmap (pair × TF)</h3>""")
    if not symbols:
        html.append("<div class='small'>Aucune matrice.</div>")
    html.append("<table><thead><tr><th></th>")
    for tf in tfs: html.append(f"<th>{tf}</th>")
    html.append("</tr></thead><tbody>")
    for (s, line) in matrix:
        html.append(f"<tr><th style='text-align:left'>{s}</th>")
        for sig in line: html.append(cell(sig))
        html.append("</tr>")
    html.append("</tbody></table></div>")
    html.append("""<div class="card"><h3>Derniers signaux</h3>
<table><thead><tr><th>UTC</th><th>Symbol</th><th>TF</th><th>Signal</th><th>Détails</th></tr></thead><tbody>""")
    for r in latest:
        ts = time.strftime("%H:%M:%S", time.gmtime(int(r["ts"])))
        html.append(f"<tr><td>{ts}</td><td>{r.get('symbol','')}</td><td>{r.get('tf','')}</td><td>{r.get('signal','')}</td><td class='small'>{r.get('details','')}</td></tr>")
    html.append("</tbody></table></div></body></html>")
    return "".join(html)

def main():
    rows = load_rows(CSV)
    syms, tfs, matrix, counts = build_heatmap(rows)
    latest = top_signals(rows, 25)
    html = render(syms, tfs, matrix, counts, latest)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f: f.write(html)

if __name__ == "__main__":
    main()
