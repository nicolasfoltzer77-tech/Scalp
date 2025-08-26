#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Génère un #!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import os, json, time, yaml

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CFG_PATH   = os.path.join(REPO_ROOT, "engine", "config", "config.yaml")

def load_yaml(p, missing_ok=False):
    if missing_ok and not os.path.isfile(p): return {}
    with open(p, "r", encoding="utf-8") as f: return yaml.safe_load(f) or {}

def load_json(p, missing_ok=False):
    if missing_ok and not os.path.isfile(p): return {}
    with open(p, "r", encoding="utf-8") as f: return json.load(f)

def h(fmt_dt=True):
    ts = time.gmtime()
    s = time.strftime("%Y-%m-%d %H:%M:%S", ts) + " UTC"
    return s

def badge(label, val, color):
    return f"""<span style="display:inline-block;margin:4px 8px;padding:4px 10px;border-radius:14px;background:{color};color:#fff;font-weight:600;">{label}: {val}</span>"""

def render():
    cfg = load_yaml(CFG_PATH, missing_ok=True)
    rt = cfg.get("runtime", {}) if isinstance(cfg, dict) else {}
    reports_dir = rt.get("reports_dir", "/notebooks/scalp_data/reports")

    summary = load_json(os.path.join(reports_dir, "summary.json"), missing_ok=True) or {"rows":[],"meta":{}}
    status  = load_json(os.path.join(reports_dir, "status.json"),  missing_ok=True) or {"counts":{},"matrix":[]}
    last    = load_json(os.path.join(reports_dir, "last_errors.json"), missing_ok=True) or {}

    counts = status.get("counts", {})
    matrix = status.get("matrix", [])
    tf_list = list(rt.get("tf_list", ["1m","5m","15m"]))

    # TOP 20 (déjà construit côté backtest → summary.rows)
    rows = summary.get("rows", [])
    rows_sorted = sorted(rows, key=lambda r: (r.get("pf",0)*2 + r.get("sharpe",0)*0.5 + r.get("wr",0)*0.5 - r.get("mdd",1)*1.5), reverse=True)[:20]

    # HTML minimal propre
    html = []
    html.append("<!doctype html><meta charset='utf-8'><title>SCALP — Dashboard</title>")
    html.append("""
    <style>
      body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; color:#111;}
      h1 { font-size: 32px; margin: 0 0 12px 0;}
      .card { border:1px solid #e8e8e8; border-radius:10px; padding:16px 18px; margin:18px 0; }
      table { border-collapse: collapse; width: 100%; }
      th, td { border: 1px solid #eee; padding: 6px 8px; text-align: left; }
      th { background: #fafafa; }
      .MIS { color:#666; font-weight:700; }
      .OLD { color:#d90000; font-weight:700; }
      .DAT { color:#b88600; font-weight:700; }
      .OK  { color:#0a910a; font-weight:700; }
      small { color:#6b7280; }
    </style>
    """)
    html.append(f"<h1>SCALP — Dashboard <small>({h()})</small></h1>")

    # === STATUT DATA ===
    html.append('<div class="card"><h2>Statut des données (pair × TF)</h2>')
    html.append(badge("MIS", counts.get("MIS",0), "#6b7280"))
    html.append(badge("OLD", counts.get("OLD",0), "#d90000"))
    html.append(badge("DAT", counts.get("DAT",0), "#b88600"))
    html.append(badge("OK",  counts.get("OK",0),  "#0a910a"))
    html.append("<div style='height:8px'></div>")

    if matrix:
        html.append("<table><thead><tr><th>PAIR</th>" + "".join(f"<th>{tf}</th>" for tf in tf_list) + "</tr></thead><tbody>")
        for row in matrix:
            html.append("<tr><td><b>{}</b></td>{}</tr>".format(
                row["pair"],
                "".join(f"<td class='{row.get(tf,'MIS')}'>{row.get(tf,'MIS')}</td>" for tf in tf_list)
            ))
        html.append("</tbody></table>")
    else:
        html.append("<div>Aucune matrice (status.json manquant).</div>")
    html.append("</div>")

    # === TOP 20 ===
    html.append('<div class="card"><h2>TOP 20 (policy=' + rt.get("risk_mode","normal") + ")</h2>")
    if rows_sorted:
        html.append("<table><thead><tr><th>#</th><th>PAIR</th><th>TF</th><th>PF</th><th>MDD</th><th>TR</th><th>WR</th><th>Sharpe</th></tr></thead><tbody>")
        for i, r in enumerate(rows_sorted, 1):
            html.append(f"<tr><td>{i}</td><td>{r['pair']}</td><td>{r['tf']}</td>"
                        f"<td>{r['pf']:.3f}</td><td>{r['mdd']:.1%}</td><td>{r['trades']}</td><td>{r['wr']:.1%}</td><td>{r['sharpe']:.2f}</td></tr>")
        html.append("</tbody></table>")
    else:
        html.append("<div>Aucun résultat TOP.</div>")
    html.append("</div>")

    # === Dernières actions ===
    html.append('<div class="card"><h2>Dernières actions</h2>')
    if last:
        html.append("<pre style='white-space:pre-wrap;font-size:14px;background:#fafafa;padding:10px;border-radius:8px;border:1px solid #eee;'>")
        html.append(json.dumps(last, ensure_ascii=False, indent=2))
        html.append("</pre>")
    else:
        html.append("<div>Aucune info (last_errors.json manquant).</div>")
    html.append("</div>")

    return "\n".join(html)

def main():
    out = os.path.join(REPO_ROOT, "dashboard.html")  # à la racine
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(render())
    print(f"[render] Dashboard écrit → {out}")

if __name__ == "__main__":
    main() HTML statique (racine) + écrit dashboard_url.txt (localhost + ngrok).
"""

from __future__ import annotations
import os, sys, json, yaml, importlib, subprocess
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPORTS_DIR  = os.getenv("SCALP_REPORTS_DIR", "/notebooks/scalp_data/reports")

SUMMARY     = os.path.join(REPORTS_DIR, "summary.json")
STRAT_NEXT  = os.path.join(REPORTS_DIR, "strategies.yml.next")
STRAT_CURR  = os.path.join(PROJECT_ROOT, "engine", "config", "strategies.yml")
CONFIG_YAML = os.path.join(PROJECT_ROOT, "engine", "config", "config.yaml")

OUT_HTML   = os.path.join(PROJECT_ROOT, "dashboard.html")
OUT_URLTXT = os.path.join(PROJECT_ROOT, "dashboard_url.txt")

TOP_K = int(os.getenv("SCALP_DASH_TOPK", "20"))

def _log(m): print(f"[render] {m}")

NEEDED = ["plotly","altair","pyarrow","pandas"]
def _ensure_libs():
    miss=[]
    for p in NEEDED:
        try: importlib.import_module(p)
        except Exception: miss.append(p)
    if miss:
        _log(f"install pkgs via pip: {miss}")
        try: subprocess.check_call([sys.executable, "-m", "pip", "install"] + miss)
        except subprocess.CalledProcessError as e:
            _log(f"pip install failed ({e.returncode}) — fallback simple HTML.")

def _load_json(p): 
    if not os.path.isfile(p): return {}
    return json.load(open(p,"r",encoding="utf-8"))

def _load_yaml(p, missing_ok=True):
    if missing_ok and not os.path.isfile(p): return {}
    import yaml
    return yaml.safe_load(open(p,"r",encoding="utf-8")) or {}

def _score(r):
    pf=float(r.get("pf",0)); mdd=float(r.get("mdd",1)); sh=float(r.get("sharpe",0)); wr=float(r.get("wr",0))
    return pf*2.0 + sh*0.5 + wr*0.5 - mdd*1.5

def _esc(s): 
    s=str(s); 
    return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;").replace("'","&#39;")

def _render_simple_table(rows, k):
    head = "<tr><th>RANK</th><th>PAIR</th><th>TF</th><th>PF</th><th>MDD</th><th>TR</th><th>WR</th><th>Sharpe</th></tr>"
    body=[]
    for i,r in enumerate(rows[:k],1):
        body.append(f"<tr><td>{i}</td><td>{_esc(r['pair'])}</td><td>{_esc(r['tf'])}</td>"
                    f"<td>{float(r.get('pf',0)):.3f}</td><td>{float(r.get('mdd',0))*100:.1f}%</td>"
                    f"<td>{int(r.get('trades',0))}</td><td>{float(r.get('wr',0))*100:.1f}%</td>"
                    f"<td>{float(r.get('sharpe',0)):.3f}</td></tr>")
    return f"<table border='1' cellspacing='0' cellpadding='6'>{head}{''.join(body)}</table>"

def _build_urls():
    # port HTTP local (http.server)
    port = 8888
    try:
        cfg = _load_yaml(CONFIG_YAML, True) or {}
        port = int(cfg.get("runtime", {}).get("html_port", port))
    except Exception:
        pass
    urls = [f"http://localhost:{port}/dashboard.html"]

    # url ngrok depuis env ou fichier
    ngrok = os.environ.get("NGROK_URL","").strip()
    if not ngrok:
        path = os.path.join(PROJECT_ROOT, "ngrok_url.txt")
        if os.path.isfile(path):
            ngrok = open(path,"r",encoding="utf-8").read().strip().splitlines()[0]
    if ngrok:
        ngrok = ngrok.rstrip("/")
        urls.append(f"{ngrok}/dashboard.html")
    return urls

def _write_urls_file():
    urls = _build_urls()
    with open(OUT_URLTXT, "w", encoding="utf-8") as f:
        for u in urls: f.write(u+"\n")
    _log(f"URLs écrites → {OUT_URLTXT}")

def generate():
    _ensure_libs()
    try:
        import pandas as pd
        px = importlib.import_module("plotly.express")
        go = importlib.import_module("plotly.graph_objects")
        PLOTLY_OK=True
    except Exception:
        PLOTLY_OK=False
        try: import pandas as pd
        except Exception:
            _log("pandas indisponible — abandon rendu."); _write_urls_file(); return

    sm = _load_json(SUMMARY); rows = sm.get("rows", [])
    risk_mode = sm.get("risk_mode","normal")
    rows_sorted = sorted(rows, key=_score, reverse=True)

    if PLOTLY_OK and rows_sorted:
        import numpy as np  # noqa
        df = pd.DataFrame([{
            "RANK": i+1, "PAIR": r["pair"], "TF": r["tf"],
            "PF": round(float(r.get("pf",0)),3),
            "MDD": float(r.get("mdd",0))*100.0,
            "TR": int(r.get("trades",0)),
            "WR": float(r.get("wr",0))*100.0,
            "Sharpe": round(float(r.get("sharpe",0)),3),
        } for i,r in enumerate(rows_sorted[:TOP_K])])
        table_fig = go.Figure(data=[go.Table(
            header=dict(values=list(df.columns),
                        fill_color="#1f2937", font=dict(color="white"), align="left"),
            cells=dict(values=[df[c] for c in df.columns], align="left")
        )])
        table_fig.update_layout(margin=dict(l=0,r=0,t=10,b=0))
        top_html = table_fig.to_html(full_html=False, include_plotlyjs="cdn")

        df_hm = pd.DataFrame([{"pair": r["pair"], "tf": r["tf"], "pf": r.get("pf",0)} for r in rows_sorted])
        if not df_hm.empty:
            order = ["1m","3m","5m","15m","30m","1h","4h","1d"]
            df_hm["tf"] = pd.Categorical(df_hm["tf"], categories=order, ordered=True)
            pt = df_hm.pivot_table(index="pair", columns="tf", values="pf", aggfunc="max")
            if not pt.empty:
                hm = px.imshow(pt, color_continuous_scale="RdYlGn", origin="lower",
                               labels=dict(color="PF"), aspect="auto")
                hm.update_layout(margin=dict(l=0,r=0,t=30,b=0))
                heatmap_html = hm.to_html(full_html=False, include_plotlyjs=False)
            else:
                heatmap_html = "<div>Pas de données pour la heatmap PF.</div>"
        else:
            heatmap_html = "<div>Pas de données pour la heatmap PF.</div>"
    else:
        top_html = _render_simple_table(rows_sorted, TOP_K) if rows_sorted else "<div>Aucun résultat TOP.</div>"
        heatmap_html = "<div>Heatmap indisponible (plotly absent ou aucune donnée).</div>"

    html = f"""<!DOCTYPE html>
<html lang="fr"><head>
<meta charset="utf-8"/>
<title>SCALP — Dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<style>
body {{ font-family: system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,"Helvetica Neue",Arial; margin:20px; }}
h1 {{ color:#111827; }}
.section {{ margin: 24px 0; }}
.card {{ border:1px solid #e5e7eb; border-radius:8px; padding:16px; }}
</style>
</head>
<body>
<h1>SCALP — Dashboard <small>({datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")})</small></h1>
<div class="section card"><h2>TOP {TOP_K} (policy={risk_mode})</h2>{top_html}</div>
<div class="section card"><h2>Heatmap PF par paire × TF</h2>{heatmap_html}</div>
</body></html>"""
    open(OUT_HTML,"w",encoding="utf-8").write(html)
    _log(f"Dashboard écrit → {OUT_HTML}")
    _write_urls_file()

if __name__ == "__main__":
    generate()