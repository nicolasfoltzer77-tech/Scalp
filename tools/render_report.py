#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Génère un dashboard HTML statique (à la racine du repo) et écrit des URL d'accès.
Sorties:
  ./dashboard.html
  ./dashboard_url.txt   (localhost + NGROK si dispo)

Si plotly/altair/pyarrow/pandas sont absents, installe à la volée.
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

def _log(msg: str): print(f"[render] {msg}")

# ---------- auto-install
NEEDED = ["plotly", "altair", "pyarrow", "pandas"]
def _ensure_libs():
    missing = []
    for pkg in NEEDED:
        try: importlib.import_module(pkg)
        except Exception: missing.append(pkg)
    if missing:
        _log(f"install pkgs via pip: {missing}")
        try: subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
        except subprocess.CalledProcessError as e:
            _log(f"pip install failed ({e.returncode}) — fallback simple HTML.")

# ---------- helpers
def _load_json(path):
    if not os.path.isfile(path): return {}
    with open(path, "r", encoding="utf-8") as f: return json.load(f)

def _load_yaml(path, missing_ok=True):
    if missing_ok and not os.path.isfile(path): return {}
    with open(path, "r", encoding="utf-8") as f: return yaml.safe_load(f) or {}

def _score(r):
    pf=float(r.get("pf",0)); mdd=float(r.get("mdd",1)); sh=float(r.get("sharpe",0)); wr=float(r.get("wr",0))
    return pf*2.0 + sh*0.5 + wr*0.5 - mdd*1.5

def _esc(s: str) -> str:
    return (str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
                   .replace('"',"&quot;").replace("'","&#39;"))

def _render_simple_table(rows_sorted, top_k:int):
    head = "<tr><th>RANK</th><th>PAIR</th><th>TF</th><th>PF</th><th>MDD</th><th>TR</th><th>WR</th><th>Sharpe</th></tr>"
    body=[]
    for i,r in enumerate(rows_sorted[:top_k],1):
        body.append(f"<tr><td>{i}</td><td>{_esc(r['pair'])}</td><td>{_esc(r['tf'])}</td>"
                    f"<td>{float(r.get('pf',0)):.3f}</td><td>{float(r.get('mdd',0))*100:.1f}%</td>"
                    f"<td>{int(r.get('trades',0))}</td><td>{float(r.get('wr',0))*100:.1f}%</td>"
                    f"<td>{float(r.get('sharpe',0)):.3f}</td></tr>")
    return f"<table border='1' cellspacing='0' cellpadding='6'>{head}{''.join(body)}</table>"

def _build_urls():
    """Construit les URL utiles pour ouvrir le HTML local/à distance (ngrok)."""
    # port HTTP local (pour http.server), par défaut 8888 (peut venir de config.yaml)
    port = 8888
    try:
        cfg = _load_yaml(CONFIG_YAML, missing_ok=True) or {}
        port = int(cfg.get("runtime", {}).get("html_port", port))
    except Exception:
        pass

    urls = [f"http://localhost:{port}/dashboard.html"]
    # support NGROK_URL via env ou via fichier ngrok_url.txt à la racine
    ngrok = os.environ.get("NGROK_URL", "").strip()
    if not ngrok:
        try:
            path = os.path.join(PROJECT_ROOT, "ngrok_url.txt")
            if os.path.isfile(path):
                ngrok = open(path, "r", encoding="utf-8").read().strip().splitlines()[0]
        except Exception:
            pass
    if ngrok:
        ngrok = ngrok.rstrip("/")
        urls.append(f"{ngrok}/dashboard.html")
    return urls

def _write_urls_file():
    urls = _build_urls()
    with open(OUT_URLTXT, "w", encoding="utf-8") as f:
        for u in urls: f.write(u+"\n")
    _log(f"URLs écrites → {OUT_URLTXT}")

# ---------- main
def generate():
    _ensure_libs()
    try:
        import pandas as pd
        px = importlib.import_module("plotly.express")
        go = importlib.import_module("plotly.graph_objects")
        PLOTLY_OK = True
    except Exception:
        PLOTLY_OK = False
        try: import pandas as pd  # au moins pour fallback
        except Exception:
            _log("pandas indisponible — abandon rendu.")
            _write_urls_file()
            return

    sm = _load_json(SUMMARY)
    rows = sm.get("rows", [])
    risk_mode = sm.get("risk_mode","normal")
    rows_sorted = sorted(rows, key=_score, reverse=True)

    # TOP table
    if PLOTLY_OK and rows_sorted:
        import numpy as np  # noqa
        df_top = pd.DataFrame([{
            "RANK": i+1,
            "PAIR": r["pair"], "TF": r["tf"],
            "PF": round(float(r.get("pf",0)),3),
            "MDD": float(r.get("mdd",0))*100.0,
            "TR": int(r.get("trades",0)),
            "WR": float(r.get("wr",0))*100.0,
            "Sharpe": round(float(r.get("sharpe",0)),3),
        } for i,r in enumerate(rows_sorted[:TOP_K])])
        table_fig = go.Figure(data=[go.Table(
            header=dict(values=list(df_top.columns),
                        fill_color="#1f2937", font=dict(color="white"), align="left"),
            cells=dict(values=[df_top[c] for c in df_top.columns], align="left")
        )])
        table_fig.update_layout(margin=dict(l=0,r=0,t=10,b=0))
        top_html = table_fig.to_html(full_html=False, include_plotlyjs="cdn")
    else:
        top_html = _render_simple_table(rows_sorted, TOP_K) if rows_sorted else "<div>Aucun résultat TOP.</div>"

    # Heatmap PF
    if PLOTLY_OK and rows_sorted:
        df_hm = pd.DataFrame([{"pair": r["pair"], "tf": r["tf"], "pf": r.get("pf",0)} for r in rows_sorted])
        order = ["1m","3m","5m","15m","30m","1h","4h","1d"]
        df_hm["tf"] = pd.Categorical(df_hm["tf"], categories=order, ordered=True)
        pt = df_hm.pivot_table(index="pair", columns="tf", values="pf", aggfunc="max")
        if pt.empty:
            heatmap_html = "<div>Pas de données pour la heatmap PF.</div>"
        else:
            hm = px.imshow(pt, color_continuous_scale="RdYlGn", origin="lower",
                           labels=dict(color="PF"), aspect="auto")
            hm.update_layout(margin=dict(l=0,r=0,t=30,b=0))
            heatmap_html = hm.to_html(full_html=False, include_plotlyjs=False)
    else:
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
<div class="section card">
  <h2>TOP {TOP_K} (policy={risk_mode})</h2>
  {top_html}
</div>
<div class="section card">
  <h2>Heatmap PF par paire × TF</h2>
  {heatmap_html}
</div>
</body></html>
"""
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    _log(f"Dashboard écrit → {OUT_HTML}")

    _write_urls_file()

if __name__ == "__main__":
    try:
        generate()
    except Exception as e:
        _log(f"erreur fatale: {e}")
        sys.exit(1)