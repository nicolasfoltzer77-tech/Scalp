#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import csv, os, time, json, html
from collections import defaultdict

CSV_PATH = "/opt/scalp/var/dashboard/signals.csv"
OUT_HTML = "/opt/scalp/dashboard.html"
PUBLISH_HTML = "/opt/scalp/docs/index.html"
REFRESH_SEC = int(os.getenv("SCALP_DASH_REFRESH", "10"))
TF_ORDER = ["1m","5m","15m"]
AGE_OLD = 30*60  # >30 min => OLD

BADGES = {
    "BUY":  ("#16a34a", "#052e16"),
    "SELL": ("#dc2626", "#450a0a"),
    "HOLD": ("#737373", "#171717"),
}

def read_rows(path):
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                ts = int(row.get("ts") or 0)
                sym = row.get("symbol","").upper()
                tf = row.get("tf","")
                sig = row.get("signal","HOLD").upper()
                det = row.get("details","")
                if not ts or not sym or not tf:
                    continue
                rows.append({"ts":ts,"symbol":sym,"tf":tf,"signal":sig,"details":det})
            except Exception:
                # ligne cassée -> on ignore
                continue
    return rows

def last_per_pair_tf(rows):
    best = {}
    for r in rows:
        k = (r["symbol"], r["tf"])
        if k not in best or r["ts"] > best[k]["ts"]:
            best[k] = r
    return best

def counters(best):
    now = int(time.time())
    seen = set(best.keys())
    syms = sorted({s for (s,_) in seen})
    tfs  = sorted({t for (_,t) in seen}, key=lambda x: (TF_ORDER.index(x) if x in TF_ORDER else 99, x))

    total_slots = len(syms) * len(tfs) if syms and tfs else len(seen)
    mis = total_slots - len(seen)

    old = 0
    ok  = 0
    for r in best.values():
        age = now - r["ts"]
        if age > AGE_OLD:
            old += 1
        else:
            ok += 1
    return {"MIS":mis,"OLD":old,"DAT":0,"OK":ok}

def badge(sig):
    fg,bg = BADGES.get(sig, BADGES["HOLD"])
    return f'<span class="pill" style="color:{fg};background:{bg};">{html.escape(sig)}</span>'

def fmt_ago(ts):
    d = int(time.time()) - int(ts)
    if d < 90: return f"{d}s"
    m = d//60
    if m < 90: return f"{m}m"
    h = m//60
    return f"{h}h"

def render(rows):
    best = last_per_pair_tf(rows)
    cnt = counters(best)

    syms = sorted({s for (s,_) in best.keys()})
    tfs  = [tf for tf in TF_ORDER if any((_,tf) in best for _ in syms)]
    now = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

    # derniers signaux (20)
    last = sorted(rows, key=lambda r: r["ts"], reverse=True)[:20]

    css = f"""
    :root {{
      --bg:#0b0f14; --panel:#10151c; --text:#e5e7eb; --muted:#9ca3af; --accent:#38bdf8;
      --ok:#22c55e; --old:#f97316; --mis:#9ca3af; --dat:#eab308;
    }}
    *{{box-sizing:border-box}} html,body{{margin:0;padding:0;background:var(--bg);color:var(--text);font:14px/1.45 system-ui, -apple-system, Segoe UI, Roboto, sans-serif}}
    a{{color:var(--accent);text-decoration:none}}
    .wrap{{max-width:1100px;margin:0 auto;padding:16px}}
    header h1{{margin:0 0 6px 0;font-size:24px}}
    header .meta{{color:var(--muted);font-size:12px;display:flex;gap:12px;align-items:center}}
    .tiny{{opacity:.7;font-size:12px}}
    .pill{{display:inline-block;padding:.15rem .5rem;border-radius:999px;font-weight:600;letter-spacing:.3px}}
    .grid{{display:grid;gap:14px}}
    .card{{background:var(--panel);border-radius:12px;padding:14px}}
    .kpis{{display:flex;gap:10px;flex-wrap:wrap}}
    .kpi{{display:flex;gap:8px;align-items:center;background:#0f172a;border-radius:999px;padding:.25rem .6rem;font-size:12px}}
    .kpi .dot{{width:10px;height:10px;border-radius:50%}}
    .t{{overflow:auto;border-radius:8px;border:1px solid #1f2937}}
    table{{border-collapse:collapse;width:100%;min-width:560px}}
    th,td{{padding:.5rem .6rem;border-bottom:1px solid #1f2937;white-space:nowrap}}
    th{{text-align:left;color:#cbd5e1;background:#0f172a;position:sticky;top:0}}
    tr:hover td{{background:#0e1726}}
    .right{{text-align:right}}
    .muted{{color:var(--muted)}}
    footer{{margin:10px 0 0;color:var(--muted);font-size:12px}}
    .countdown{{font-variant-numeric:tabular-nums;}}
    """

    js = f"""
    <script>
    const REFRESH={REFRESH_SEC};
    let s=REFRESH;
    function tick(){{
      try{{document.getElementById('count').textContent=s}}catch(e){{}}
      if(--s<0) location.reload();
    }} setInterval(tick,1000);
    </script>
    """

    # heatmap
    thead = "<tr><th>Pair \\ TF</th>" + "".join(f"<th>{tf}</th>" for tf in tfs) + "</tr>"
    rows_html = []
    for sym in syms:
        tds = [f"<td class='muted'>{sym}</td>"]
        for tf in tfs:
            r = best.get((sym, tf))
            if not r:
                tds.append("<td><span class='pill' style='color:#9ca3af;background:#111827;'>N/A</span></td>")
            else:
                tds.append(f"<td>{badge(r['signal'])}</td>")
        rows_html.append("<tr>" + "".join(tds) + "</tr>")
    heatmap = f"<div class='t'><table><thead>{thead}</thead><tbody>{''.join(rows_html)}</tbody></table></div>"

    # derniers signaux
    last_rows = []
    for r in last:
        last_rows.append(
            "<tr>"
            f"<td class='muted'>{time.strftime('%H:%M:%S', time.gmtime(r['ts']))}</td>"
            f"<td>{html.escape(r['symbol'])}</td>"
            f"<td>{html.escape(r['tf'])}</td>"
            f"<td>{badge(r['signal'])}</td>"
            f"<td class='muted'>{html.escape(r.get('details',''))}</td>"
            "</tr>"
        )
    last_tbl = (
        "<div class='t'><table><thead><tr>"
        "<th>UTC</th><th>Symbol</th><th>TF</th><th>Signal</th><th>Details</th>"
        "</tr></thead><tbody>" + "".join(last_rows) + "</tbody></table></div>"
    )

    html_out = f"""<!doctype html>
<html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SCALP — Dashboard</title>
<style>{css}</style>
<div class="wrap">
<header>
  <h1>SCALP — Dashboard</h1>
  <div class="meta">
    <span class="tiny">({now})</span>
    <span class="tiny">auto-refresh <span class="countdown" id="count">{REFRESH_SEC}</span>s</span>
    <span class="tiny"><a href="/signals.json">signals.json</a></span>
  </div>
</header>

<div class="grid">
  <div class="card">
    <div class="kpis">
      <div class="kpi"><span class="dot" style="background:#9ca3af"></span><b>MIS:</b> {cnt['MIS']}</div>
      <div class="kpi"><span class="dot" style="background:#ef4444"></span><b>OLD:</b> {cnt['OLD']}</div>
      <div class="kpi"><span class="dot" style="background:#eab308"></span><b>DAT:</b> {cnt['DAT']}</div>
      <div class="kpi"><span class="dot" style="background:#22c55e"></span><b>OK:</b> {cnt['OK']}</div>
    </div>
    <div class="tiny" style="margin-top:6px;">OK = dernière valeur BUY/SELL/HOLD • MIS = aucune donnée • OLD &gt; 30 min</div>
  </div>

  <div class="card">
    <h3 style="margin:0 0 10px">Heatmap (pair × TF)</h3>
    {heatmap}
  </div>

  <div class="card">
    <h3 style="margin:0 0 10px">Derniers signaux</h3>
    {last_tbl}
  </div>
</div>

<footer>© SCALP · rendu côté serveur · nginx</footer>
</div>
{js}
</html>"""
    return html_out

def main():
    rows = read_rows(CSV_PATH)
    html_doc = render(rows)
    # écrire l'artefact local + la version publiée
    for p in (OUT_HTML, PUBLISH_HTML):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(html_doc)
    print(f"[build] HTML -> {PUBLISH_HTML} ({len(rows)} rows)")

if __name__ == "__main__":
    main()
