#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv, os, time, html, itertools
from collections import defaultdict, deque

BASE = "/opt/scalp"
CSV_PATH = f"{BASE}/var/dashboard/signals.csv"
OUT_HTML = f"{BASE}/dashboard.html"

NOW = int(time.time())
UTC = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(NOW))

def read_rows(path):
    if not os.path.exists(path): return []
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return list(r)

def classify_age(ts):
    try:
        ts = int(ts)
    except Exception:
        return "MIS"
    age = NOW - ts
    if age > 30*60:  # > 30 minutes
        return "OLD"
    return "DAT"

def build_heatmap(rows):
    # garde le dernier signal (par symbol × tf)
    last = {}
    for r in rows:
        try:
            ts  = int(r.get("ts") or 0)
            sym = r.get("symbol") or "?"
            tf  = r.get("tf") or "?"
            sig = r.get("signal") or "HOLD"
        except Exception:
            continue
        key = (sym, tf)
        if key not in last or ts > last[key]["ts"]:
            last[key] = {"ts": ts, "sig": sig}

    syms = sorted(set(s for s,_ in last.keys()))
    tfs  = sorted(set(t for _,t in last.keys()),
                  key=lambda x: ["1m","5m","15m","1h","4h","1d"].index(x) if x in ["1m","5m","15m","1h","4h","1d"] else 99)

    matrix = []
    for s in syms:
        row = []
        for t in tfs:
            cell = last.get((s,t))
            row.append(cell["sig"] if cell else "")
        matrix.append((s,row))
    return syms, tfs, matrix

def counters(rows):
    c = {"MIS":0,"OLD":0,"DAT":0,"OK":0}
    # OK = on a une dernière valeur BUY/SELL/HOLD (donc présente) et récente
    latest = {}
    for r in rows:
        sym, tf = r.get("symbol"), r.get("tf")
        ts = int(r.get("ts") or 0)
        if not (sym and tf and ts): continue
        k = (sym, tf)
        if k not in latest or ts > latest[k]["ts"]:
            latest[k] = {"ts": ts, "signal": r.get("signal","HOLD")}
    for k, v in latest.items():
        age = classify_age(v["ts"])
        if age == "MIS": c["MIS"] += 1
        elif age == "OLD": c["OLD"] += 1
        else:
            c["DAT"] += 1
            c["OK"]  += 1
    return c

def recent(rows, n=30):
    # tri décroissant par ts
    clean = []
    for r in rows:
        try:
            clean.append({
                "ts": int(r.get("ts") or 0),
                "symbol": r.get("symbol","?"),
                "tf": r.get("tf","?"),
                "signal": r.get("signal","HOLD"),
                "details": r.get("details","")
            })
        except Exception:
            pass
    clean.sort(key=lambda x: x["ts"], reverse=True)
    return clean[:n]

def sig_class(s):
    s = (s or "").upper()
    return {"BUY":"buy","SELL":"sell","HOLD":"hold"}.get(s,"hold")

def render(rows):
    cnt = counters(rows)
    syms, tfs, matrix = build_heatmap(rows)
    last = recent(rows, 50)

    css = """
    <style>
      :root{--bg:#0b0d12;--fg:#e6edf3;--mut:#8b949e;--card:#111520;--br:#21262d;
            --ok:#2ea043;--warn:#d29922;--bad:#f85149;
            --buy:#2ea043;--sell:#f85149;--hold:#6e7681}
      *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
         font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Ubuntu}
      .wrap{max-width:1180px;margin:0 auto;padding:28px}
      h1{font-size:42px;margin:6px 0 18px}
      .sub{color:var(--mut);font-weight:600;margin-bottom:22px}
      .cards{display:grid;grid-template-columns:1fr;gap:16px}
      @media(min-width:900px){.cards{grid-template-columns:1fr}}
      .card{background:var(--card);border:1px solid var(--br);border-radius:12px;padding:16px}
      .kpis{display:flex;gap:14px;flex-wrap:wrap;margin-top:10px}
      .pill{border-radius:20px;padding:8px 14px;font-weight:700}
      .mis{background:#6e768144;color:#fff}.old{background:var(--bad);color:#fff}
      .dat{background:var(--warn);color:#000}.ok{background:var(--ok);color:#000}
      table{width:100%;border-collapse:collapse}
      th,td{padding:10px;border-bottom:1px solid var(--br);text-align:left}
      th{color:var(--mut);font-weight:700}
      .sig.buy{color:var(--buy);font-weight:800}
      .sig.sell{color:var(--sell);font-weight:800}
      .sig.hold{color:var(--hold);font-weight:700}
      .hm{overflow:auto}
      .hm table td{min-width:78px;text-align:center}
      .cell{display:inline-block;padding:6px 10px;border-radius:10px;background:#30363d33}
    </style>
    """

    def _cnt(label, val, cls):
        return f'<span class="pill {cls.lower()}">{label}: {val}</span>'

    # heatmap header
    hm_head = "".join(f"<th>{html.escape(tf)}</th>" for tf in tfs) or "<th>(aucun TF)</th>"
    hm_rows = []
    for s,row in matrix:
        cells = "".join(f'<td><span class="cell {sig_class(v)}">{html.escape(v)}</span></td>' if v else "<td></td>" for v in row)
        hm_rows.append(f"<tr><th>{html.escape(s)}</th>{cells}</tr>")
    hm_html = f"""
      <div class="hm">
        <table>
          <thead><tr><th>Pair \\ TF</th>{hm_head}</tr></thead>
          <tbody>{"".join(hm_rows) if hm_rows else '<tr><td colspan="99">Aucune matrice.</td></tr>'}</tbody>
        </table>
      </div>
    """

    # recent table
    rec_rows = []
    for r in last:
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(r["ts"])) if r["ts"] else "-"
        rec_rows.append(
            f"<tr><td>{ts}</td>"
            f"<td>{html.escape(r['symbol'])}</td>"
            f"<td>{html.escape(r['tf'])}</td>"
            f"<td class='sig {sig_class(r['signal'])}'>{html.escape(r['signal'])}</td>"
            f"<td>{html.escape(r['details'] or '')}</td></tr>"
        )
    rec_html = "".join(rec_rows) or "<tr><td colspan='5'>Aucun signal.</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SCALP — Dashboard</title>
<meta http-equiv="refresh" content="5">
{css}
<body><div class="wrap">
<h1>SCALP — Dashboard</h1>
<div class="sub">({UTC} UTC)</div>

<div class="cards">

  <section class="card">
    <h2>Compteurs</h2>
    <div class="kpis">
      {_cnt("MIS", cnt["MIS"], "MIS")}
      {_cnt("OLD", cnt["OLD"], "OLD")}
      {_cnt("DAT", cnt["DAT"], "DAT")}
      {_cnt("OK",  cnt["OK"],  "OK")}
    </div>
    <div style="margin-top:8px;color:#8b949e">OK = dernière valeur BUY/SELL/HOLD • MIS = aucune donnée</div>
  </section>

  <section class="card">
    <h2>Heatmap (pair × TF)</h2>
    {hm_html}
  </section>

  <section class="card">
    <h2>Derniers signaux</h2>
    <table>
      <thead><tr><th>UTC</th><th>Symbol</th><th>TF</th><th>Signal</th><th>Details</th></tr></thead>
      <tbody>{rec_html}</tbody>
    </table>
  </section>

</div>
</div></body></html>
"""

def main():
    rows = read_rows(CSV_PATH)
    html = render(rows)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

if __name__ == "__main__":
    main()
