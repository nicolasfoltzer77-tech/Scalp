from __future__ import annotations
import csv, os, time, json
from collections import defaultdict, deque

CSV = "/opt/scalp/var/dashboard/signals.csv"
OUT = "/opt/scalp/dashboard.html"
NOW = int(time.time())

def load_rows(path: str):
    if not os.path.exists(path): return []
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return list(r)

def classify_age(ts: int) -> str:
    age = NOW - ts
    if age > 30*60: return "OLD"   # >30 min
    return "FRESH"

def build_heatmap(rows):
    last = {}  # (symbol, tf) -> signal
    for row in rows:
        try:
            ts = int(row["ts"])
            sym = row["symbol"]; tf = row["tf"]; sig = row["signal"].upper()
            last[(sym, tf)] = (sig, ts)
        except Exception:
            continue
    symbols = sorted({s for (s,_) in last.keys()})
    tfs     = sorted({t for (_,t) in last.keys()}, key=lambda x: (len(x), x))
    matrix = []
    counts = defaultdict(int)
    for s in symbols:
        line = []
        for t in tfs:
            sig, ts = last.get((s,t), ("MIS", 0))
            if sig not in ("BUY","SELL","HOLD"): sig = "HOLD"
            if ts == 0: sig = "MIS"
            line.append(sig)
            counts[sig]+=1
        matrix.append((s, line))
    return symbols, tfs, matrix, counts

def top_signals(rows, n=15):
    dq = deque()
    for row in rows:
        try:
            row["ts"] = int(row["ts"])
            row["signal"] = row["signal"].upper()
            dq.append(row)
        except: pass
    last = list(dq)[-n:]
    last.reverse()
    return last

def render(symbols, tfs, matrix, counts, latest):
    def cell(sig):
        colors = {"BUY":"#16a34a","SELL":"#dc2626","HOLD":"#64748b","MIS":"#9ca3af"}
        return f'<td style="background:{colors.get(sig,"#9ca3af")};color:white;text-align:center;padding:6px">{sig}</td>'
    def pct(v, tot): 
        return f"{(100.0*v/tot):.0f}%" if tot else "0%"

    total = sum(counts.values())
    html = []
    html.append(f"""<!doctype html>
<html><head><meta charset="utf-8"><title>SCALP — Dashboard</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="preconnect" href="https://fonts.gstatic.com">
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Inter,Helvetica,Arial,sans-serif;margin:24px;color:#111827}}
h1{{margin:0 0 8px}}
.card{{border:1px solid #e5e7eb;border-radius:12px;padding:16px;margin:16px 0}}
.badge{{display:inline-block;padding:6px 10px;border-radius:999px;color:#fff;margin-right:8px;font-weight:600}}
.badge.gray{{background:#6b7280}} .badge.red{{background:#ef4444}}
.badge.amber{{background:#d97706}} .badge.green{{background:#16a34a}}
table{{border-collapse:separate;border-spacing:6px;}}
thead th{{font-size:12px;color:#374151}}
.small{{font-size:12px;color:#6b7280}}
</style></head><body>
<h1>SCALP — Dashboard <span class="small">({time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(NOW))})</span></h1>

<div class="card">
  <h3>Compteurs</h3>
  <span class="badge gray">MIS: {counts.get("MIS",0)}</span>
  <span class="badge red">OLD: {counts.get("OLD",0)}</span>
  <span class="badge amber">DAT: {counts.get("DAT",0)}</span>
  <span class="badge green">OK: {counts.get("BUY",0)+counts.get("SELL",0)+counts.get("HOLD",0)}</span>
  <div class="small">OK=dernière valeur BUY/SELL/HOLD • MIS=aucune donnée</div>
</div>

<div class="card">
  <h3>Heatmap (pair × TF)</h3>
  {"<div class='small'>Aucune matrice.</div>" if not symbols else ""}
  <table>
    <thead><tr><th></th>""" )
    for tf in tfs: html.append(f"<th>{tf}</th>")
    html.append("</tr></thead><tbody>")
    for (s, line) in matrix:
        html.append(f"<tr><th style='text-align:left'>{s}</th>")
        for sig in line:
            html.append(cell(sig))
        html.append("</tr>")
    html.append("</tbody></table></div>")

    html.append("""<div class="card"><h3>Derniers signaux</h3>
<table><thead><tr><th>UTC</th><th>Symbol</th><th>TF</th><th>Signal</th><th>Details</th></tr></thead><tbody>""")
    for r in latest:
        ts = time.strftime("%H:%M:%S", time.gmtime(r["ts"]))
        html.append(f"<tr><td>{ts}</td><td>{r['symbol']}</td><td>{r['tf']}</td><td>{r['signal']}</td><td class='small'>{r.get('details','')}</td></tr>")
    html.append("</tbody></table></div>")

    html.append("</body></html>")
    return "".join(html)

def main():
    rows = load_rows(CSV)
    syms,tfs,matrix,counts = build_heatmap(rows)
    latest = top_signals(rows, n=25)
    html = render(syms,tfs,matrix,counts,latest)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT,"w",encoding="utf-8") as f: f.write(html)

if __name__ == "__main__":
    main()
