#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Génère un tableau de bord HTML statique (auto‑contenu) depuis summary.json et strategies.yml(.next)
Sortie: /notebooks/scalp_data/reports/dashboard.html
- Top K par score + PF/Sharpe/MDD/Trades
- Heatmap PF par paire/TF
- Détail par paire: courbe equity si disponible (optionnel)
"""

from __future__ import annotations
import os, json, yaml, math
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

REPORTS_DIR = os.getenv("SCALP_REPORTS_DIR", "/notebooks/scalp_data/reports")
SUMMARY = os.path.join(REPORTS_DIR, "summary.json")
STRAT_NEXT = os.path.join(REPORTS_DIR, "strategies.yml.next")
STRAT_CURR = os.path.join(os.path.dirname(__file__), "..", "engine", "config", "strategies.yml")

OUT_HTML = os.path.join(REPORTS_DIR, "dashboard.html")
TOP_K = int(os.getenv("SCALP_DASH_TOPK", "20"))

def _load_json(path):
    if not os.path.isfile(path): return {}
    with open(path, "r", encoding="utf-8") as f: return json.load(f)

def _load_yaml(path, missing_ok=True):
    if missing_ok and not os.path.isfile(path): return {}
    with open(path, "r", encoding="utf-8") as f: return yaml.safe_load(f) or {}

def _score(r):
    pf = float(r.get("pf", 0)); mdd = float(r.get("mdd", 1))
    sh = float(r.get("sharpe", 0)); wr = float(r.get("wr", 0))
    return pf*2.0 + sh*0.5 + wr*0.5 - mdd*1.5

def _heatmap_df(rows):
    if not rows: return pd.DataFrame(columns=["pair","tf","pf"])
    df = pd.DataFrame([{"pair": r["pair"], "tf": r["tf"], "pf": r.get("pf",0)} for r in rows])
    # ordre TF
    order = ["1m","3m","5m","15m","30m","1h","4h","1d"]
    df["tf"] = pd.Categorical(df["tf"], categories=order, ordered=True)
    return df.pivot_table(index="pair", columns="tf", values="pf", aggfunc="max")

def _render_table(df):
    if df.empty:
        return go.Figure().to_html(full_html=False, include_plotlyjs="cdn")
    fig = go.Figure(data=[go.Table(
        header=dict(values=list(df.columns),
                    fill_color="#1f2937", font=dict(color="white"), align="left"),
        cells=dict(values=[df[c] for c in df.columns],
                   fill_color=[[("#e5f5e0" if "PASS" in str(v) else "white") for v in df.iloc[:,0]]] + 
                              [[ "white" for _ in df.index ] for _ in df.columns[1:]],
                   align="left"))
    ])
    fig.update_layout(margin=dict(l=0,r=0,t=10,b=0))
    return fig.to_html(full_html=False, include_plotlyjs="cdn")

def generate():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    sm = _load_json(SUMMARY)
    rows = sm.get("rows", [])
    risk_mode = sm.get("risk_mode", "normal")

    # TOP K
    rows_sorted = sorted(rows, key=_score, reverse=True)
    top = rows_sorted[:TOP_K]
    df_top = pd.DataFrame([{
        "RANK": i+1,
        "PAIR": r["pair"],
        "TF": r["tf"],
        "PF": round(float(r.get("pf",0)), 3),
        "MDD": f"{float(r.get('mdd',0))*100:.1f}%",
        "TR": int(r.get("trades",0)),
        "WR": f"{float(r.get('wr',0))*100:.1f}%",
        "Sharpe": round(float(r.get("sharpe",0)), 3),
    } for i, r in enumerate(top)])

    # Annoter PASS/FAIL si policy connue (copiée de jobs/promote.py)
    POLICY = {
        "conservative": {"pf": 1.4, "mdd": 0.15, "trades": 35},
        "normal":       {"pf": 1.3, "mdd": 0.20, "trades": 30},
        "aggressive":   {"pf": 1.2, "mdd": 0.30, "trades": 25},
    }
    pol = POLICY.get(risk_mode, POLICY["normal"])
    status = []
    for r in rows_sorted[:TOP_K]:
        why = []
        if r.get("pf",0) < pol["pf"]:         why.append(f"PF {r.get('pf',0):.2f}<{pol['pf']:.2f}")
        if r.get("mdd",1) > pol["mdd"]:       why.append(f"MDD {r.get('mdd',1):.2%}>{pol['mdd']:.0%}")
        if r.get("trades",0) < pol["trades"]: why.append(f"TR {r.get('trades',0)}<{pol['trades']}")
        status.append("PASS" if not why else "FAIL: " + "; ".join(why))
    if not df_top.empty:
        df_top["Status"] = status

    # Heatmap PF
    df_hm = _heatmap_df(rows)
    if not df_hm.empty:
        hm = px.imshow(df_hm, color_continuous_scale="RdYlGn", origin="lower",
                       labels=dict(color="PF"), aspect="auto")
        hm.update_layout(margin=dict(l=0,r=0,t=30,b=0))
        heatmap_html = hm.to_html(full_html=False, include_plotlyjs="cdn")
    else:
        heatmap_html = "<div>Pas de données pour la heatmap PF.</div>"

    # Liste des stratégies candidates / actives
    yml_next = _load_yaml(STRAT_NEXT)
    yml_curr = _load_yaml(os.path.abspath(STRAT_CURR))
    cand = yml_next.get("strategies", {}) if isinstance(yml_next, dict) else {}
    curr = yml_curr.get("strategies", {}) if isinstance(yml_curr, dict) else {}

    def _to_df(d):
        rows_ = []
        for k,v in (d or {}).items():
            pair, tf = (k.split(":")+[""])[:2]
            met = v.get("metrics", {})
            rows_.append({
                "PAIR": pair, "TF": tf,
                "name": v.get("name",""),
                "PF": met.get("pf",0), "MDD": met.get("mdd",0), "TR": met.get("trades",0),
                "WR": met.get("wr",0), "Sharpe": met.get("sharpe",0),
                "created_at": v.get("created_at",""), "expires_at": v.get("expires_at",""),
                "expired": v.get("expired", False)
            })
        return pd.DataFrame(rows_)
    df_cand = _to_df(cand)
    df_curr = _to_df(curr)

    # HTML assemble
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    top_html = _render_table(df_top) if not df_top.empty else "<div>Aucun résultat TOP.</div>"
    cand_html = _render_table(df_cand.sort_values(['PAIR','TF'])) if not df_cand.empty else "<div>Aucune stratégie candidate.</div>"
    curr_html = _render_table(df_curr.sort_values(['PAIR','TF'])) if not df_curr.empty else "<div>Aucune stratégie promue.</div>"

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
<h1>SCALP — Dashboard backtest <small>({now})</small></h1>
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
    print(f"[render] Dashboard écrit → {OUT_HTML}")

if __name__ == "__main__":
    generate()