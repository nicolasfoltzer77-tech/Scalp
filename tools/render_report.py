#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Génère un dashboard HTML statique et écrit une URL console copiable.
Sorties:
  /notebooks/scalp_data/reports/dashboard.html
  /notebooks/scalp_data/reports/dashboard_url.txt
"""

from __future__ import annotations
import os, sys, json, yaml, importlib, subprocess, re
from datetime import datetime

# --------- chemins / fichiers
REPORTS_DIR = os.getenv("SCALP_REPORTS_DIR", "/notebooks/scalp_data/reports")
SUMMARY     = os.path.join(REPORTS_DIR, "summary.json")
STRAT_NEXT  = os.path.join(REPORTS_DIR, "strategies.yml.next")
STRAT_CURR  = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "engine", "config", "strategies.yml"))
CONFIG_YAML = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "engine", "config", "config.yaml"))
OUT_HTML    = os.path.join(REPORTS_DIR, "dashboard.html")
OUT_URLTXT  = os.path.join(REPORTS_DIR, "dashboard_url.txt")

TOP_K       = int(os.getenv("SCALP_DASH_TOPK", "20"))

# --------- utils log
def _log(msg: str):
    print(f"[render] {msg}")

# --------- auto-install libs
NEEDED = ["plotly", "altair", "pyarrow", "pandas"]
def _ensure_libs():
    missing = []
    for pkg in NEEDED:
        try:
            importlib.import_module(pkg)
        except Exception:
            missing.append(pkg)
    if not missing:
        return
    _log(f"install pkgs via pip: {missing}")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
    except subprocess.CalledProcessError as e:
        _log(f"pip install failed (code {e.returncode}) — fallback si possible.")

# --------- helpers chargement
def _load_json(path):
    if not os.path.isfile(path): return {}
    with open(path, "r", encoding="utf-8") as f: return json.load(f)

def _load_yaml(path, missing_ok=True):
    if missing_ok and not os.path.isfile(path): return {}
    with open(path, "r", encoding="utf-8") as f: return yaml.safe_load(f) or {}

# --------- score / rendu fallback
def _score(r):
    pf = float(r.get("pf", 0)); mdd = float(r.get("mdd", 1))
    sh = float(r.get("sharpe", 0)); wr = float(r.get("wr", 0))
    return pf*2.0 + sh*0.5 + wr*0.5 - mdd*1.5

def _html_escape(s: str) -> str:
    return (s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
            .replace('"',"&quot;").replace("'","&#39;"))

def _render_simple_table(rows_sorted, top_k: int):
    head = "<tr><th>RANK</th><th>PAIR</th><th>TF</th><th>PF</th><th>MDD</th><th>TR</th><th>WR</th><th>Sharpe</th></tr>"
    body = []
    for i, r in enumerate(rows_sorted[:top_k], 1):
        body.append(
            f"<tr><td>{i}</td><td>{_html_escape(r['pair'])}</td><td>{_html_escape(r['tf'])}</td>"
            f"<td>{float(r.get('pf',0)):.3f}</td><td>{float(r.get('mdd',0))*100:.1f}%</td>"
            f"<td>{int(r.get('trades',0))}</td><td>{float(r.get('wr',0))*100:.1f}%</td>"
            f"<td>{float(r.get('sharpe',0)):.3f}</td></tr>"
        )
    return f"<table border='1' cellspacing='0' cellpadding='6'>{head}{''.join(body)}</table>"

# --------- détection NOTEBOOK_ID (fiable)
def _guess_notebook_id() -> str | None:
    """
    Ordre de priorité:
    1) env SCALP_NOTEBOOK_ID
    2) engine/config/config.yaml -> runtime.notebook_id
    3) JUPYTERHUB_SERVICE_PREFIX ou NB_PREFIX qui contiennent souvent /nbooks/<id>/
    """
    nb_id = os.getenv("SCALP_NOTEBOOK_ID")
    if nb_id:
        return nb_id

    # depuis config.yaml si présent
    try:
        cfg = _load_yaml(CONFIG_YAML, missing_ok=True) or {}
        rt = cfg.get("runtime", {}) if isinstance(cfg, dict) else {}
        nb_id = rt.get("notebook_id")
        if nb_id:
            return str(nb_id).strip()
    except Exception:
        pass

    # env JupyterHub/Gradient
    for var in ("JUPYTERHUB_SERVICE_PREFIX", "NB_PREFIX"):
        val = os.getenv(var, "")
        m = re.search(r"/nbooks/([^/]+)/", val)
        if m:
            return m.group(1)

    return None

def _build_console_urls() -> list[str]:
    """
    Renvoie une liste d’URLs possibles, la 1re est la bonne si notebook_id connu:
      https://console.paperspace.com/nbooks/<NOTEBOOK_ID>/files/scalp_data/reports/dashboard.html
    En plus, on ajoute un fallback "éditeur" si jamais /files/ est bloqué.
    """
    urls = []
    nb_id = _guess_notebook_id()
    rel = "scalp_data/reports/dashboard.html"  # chemin depuis /notebooks/

    if nb_id:
        urls.append(f"https://console.paperspace.com/nbooks/{nb_id}/files/{rel}")
        # Fallback éditeur (ouvre dans l'IDE; visible partout)
        urls.append(f"https://console.paperspace.com/nbooks/{nb_id}?file=%2F{rel}")
    else:
        # si on ne connaît pas l'ID, on met un placeholder explicite
        urls.append("https://console.paperspace.com/nbooks/<NOTEBOOK_ID>/files/scalp_data/reports/dashboard.html")
        urls.append("https://console.paperspace.com/nbooks/<NOTEBOOK_ID>?file=%2Fscalp_data%2Freports%2Fdashboard.html")

    return urls

def _write_url_hint():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    urls = _build_console_urls()
    with open(OUT_URLTXT, "w", encoding="utf-8") as f:
        for u in urls:
            f.write(u + "\n")
    _log(f"URL(s) console écrite(s) → {OUT_URLTXT}")

# --------- génération
def generate():
    os.makedirs(REPORTS_DIR, exist_ok=True)

    _ensure_libs()

    # imports post-install
    try:
        import pandas as pd
    except Exception:
        _log("pandas indisponible — abandon rendu.")
        _write_url_hint()
        return

    try:
        px = importlib.import_module("plotly.express")
        go = importlib.import_module("plotly.graph_objects")
        PLOTLY_OK = True
    except Exception:
        PLOTLY_OK = False
        _log("plotly indisponible — fallback table HTML simple.")

    sm = _load_json(SUMMARY)
    rows = sm.get("rows", [])
    risk_mode = sm.get("risk_mode", "normal")
    rows_sorted = sorted(rows, key=_score, reverse=True)

    # TOP K
    if PLOTLY_OK and rows_sorted:
        import numpy as np  # noqa
        df_top = pd.DataFrame([{
            "RANK": i+1,
            "PAIR": r["pair"],
            "TF": r["tf"],
            "PF": round(float(r.get("pf",0)), 3),
            "MDD": float(r.get("mdd",0))*100.0,
            "TR": int(r.get("trades",0)),
            "WR": float(r.get("wr",0))*100.0,
            "Sharpe": round(float(r.get("sharpe",0)), 3),
        } for i, r in enumerate(rows_sorted[:TOP_K])])
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
        if not pt.empty:
            hm = px.imshow(pt, color_continuous_scale="RdYlGn", origin="lower",
                           labels=dict(color="PF"), aspect="auto")
            hm.update_layout(margin=dict(l=0,r=0,t=30,b=0))
            heatmap_html = hm.to_html(full_html=False, include_plotlyjs=False)
        else:
            heatmap_html = "<div>Pas de données pour la heatmap PF.</div>"
    else:
        heatmap_html = "<div>Heatmap indisponible (plotly absent ou aucune donnée).</div>"

    # Tables candidates/actives
    def _to_rows(d: dict):
        out = []
        for k,v in (d or {}).items():
            pair, tf = (k.split(":")+[""])[:2]
            met = v.get("metrics", {})
            out.append({
                "PAIR": pair, "TF": tf, "name": v.get("name",""),
                "PF": met.get("pf",0), "MDD": met.get("mdd",0), "TR": met.get("trades",0),
                "WR": met.get("wr",0), "Sharpe": met.get("sharpe",0),
                "created_at": v.get("created_at",""), "expires_at": v.get("expires_at",""),
                "expired": v.get("expired", False)
            })
        return out

    yml_next = _load_yaml(STRAT_NEXT)
    yml_curr = _load_yaml(STRAT_CURR)
    cand_rows = _to_rows(yml_next.get("strategies", {}) if isinstance(yml_next, dict) else {})
    curr_rows = _to_rows(yml_curr.get("strategies", {}) if isinstance(yml_curr, dict) else {})

    def _rows_to_html(rows):
        if not rows: return "<div>Aucune stratégie.</div>"
        cols = ["PAIR","TF","name","PF","MDD","TR","WR","Sharpe","created_at","expires_at","expired"]
        head = "<tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr>"
        body = []
        for r in rows:
            body.append("<tr>" + "".join(f"<td>{_html_escape(str(r.get(c,'')))}</td>" for c in cols) + "</tr>")
        return f"<div style='overflow:auto'><table border='1' cellspacing='0' cellpadding='6'>{head}{''.join(body)}</table></div>"

    cand_html = _rows_to_html(cand_rows)
    curr_html = _rows_to_html(curr_rows)

    html = f"""<!DOCTYPE html>
<html lang="fr"><head>
<meta charset="utf-8"/>
<title>SCALP — Dashboard backtest</title>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<style>
body {{ font-family: system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,"Helvetica Neue",Arial; margin:20px; }}
h1,h2 {{ color:#111827; }}
small {{ color:#6b7280; }}
.section {{ margin: 24px 0; }}
.card {{ border:1px solid #e5e7eb; border-radius:8px; padding:16px; }}
</style>
</head>
<body>
<h1>SCALP — Dashboard backtest <small>({datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")})</small></h1>
<div class="section card">
  <h2>TOP {TOP_K} (policy={risk_mode})</h2>
  {top_html}
</div>
<div class="section card">
  <h2>Heatmap PF par paire × TF</h2>
  {heatmap_html}
</div>
<div class="section card">
  <h2>Stratégies candidates (strategies.yml.next)</h2>
  {cand_html}
</div>
<div class="section card">
  <h2>Stratégies actives (engine/config/strategies.yml)</h2>
  {curr_html}
</div>
</body></html>
"""
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    _log(f"Dashboard écrit → {OUT_HTML}")

    # URL(s) prêtes à copier (toujours)
    _write_url_hint()

if __name__ == "__main__":
    try:
        generate()
    except Exception as e:
        _log(f"erreur fatale: {e}")
        sys.exit(1)