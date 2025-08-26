#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Rendu statique en images (PNG + PDF) du dashboard backtest.
Sorties à la racine du repo:
  ./dashboard.png
  ./dashboard.pdf
"""

from __future__ import annotations
import os, sys, json, yaml, importlib, subprocess
from datetime import datetime

# --- chemins
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPORTS_DIR  = os.getenv("SCALP_REPORTS_DIR", "/notebooks/scalp_data/reports")
SUMMARY      = os.path.join(REPORTS_DIR, "summary.json")
STRAT_NEXT   = os.path.join(REPORTS_DIR, "strategies.yml.next")
STRAT_CURR   = os.path.join(PROJECT_ROOT, "engine", "config", "strategies.yml")

OUT_PNG = os.path.join(PROJECT_ROOT, "dashboard.png")
OUT_PDF = os.path.join(PROJECT_ROOT, "dashboard.pdf")

TOP_K = int(os.getenv("SCALP_DASH_TOPK", "20"))

NEEDED = ["matplotlib", "seaborn", "pandas", "pyyaml", "reportlab"]

def _log(msg: str):
    print(f"[render-img] {msg}")

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
        _log(f"pip install failed (code {e.returncode})")

def _load_json(p):
    if not os.path.isfile(p): return {}
    with open(p, "r", encoding="utf-8") as f: return json.load(f)

def _load_yaml(p, missing_ok=True):
    if missing_ok and not os.path.isfile(p): return {}
    with open(p, "r", encoding="utf-8") as f: return yaml.safe_load(f) or {}

def _score(r):
    pf = float(r.get("pf", 0)); mdd = float(r.get("mdd", 1))
    sh = float(r.get("sharpe", 0)); wr = float(r.get("wr", 0))
    return pf*2.0 + sh*0.5 + wr*0.5 - mdd*1.5

def _build_tables(pd, rows_sorted):
    # TOP K -> DataFrame
    top = rows_sorted[:TOP_K]
    if not top:
        return pd.DataFrame(), pd.DataFrame()
    df_top = pd.DataFrame([{
        "RANK": i+1,
        "PAIR": r["pair"],
        "TF": r["tf"],
        "PF": round(float(r.get("pf",0)), 3),
        "MDD%": round(float(r.get("mdd",0))*100.0, 2),
        "TR": int(r.get("trades",0)),
        "WR%": round(float(r.get("wr",0))*100.0, 1),
        "Sharpe": round(float(r.get("sharpe",0)), 3),
        "Note": round(_score(r), 3),
    } for i, r in enumerate(top)])

    # Heatmap PF: pivot pair x TF
    df_h = pd.DataFrame([{"pair": r["pair"], "tf": r["tf"], "pf": r.get("pf",0)} for r in rows_sorted])
    if df_h.empty:
        return df_top, pd.DataFrame()
    order = ["1m","3m","5m","15m","30m","1h","4h","1d"]
    df_h["tf"] = pd.Categorical(df_h["tf"], categories=order, ordered=True)
    heat = df_h.pivot_table(index="pair", columns="tf", values="pf", aggfunc="max")
    return df_top, heat

def _draw_png(pd, plt, sns, df_top, heat, risk_mode: str):
    # Figure haute résolution
    plt.close("all")
    fig = plt.figure(figsize=(14, 10), dpi=150)
    fig.suptitle(f"SCALP — Dashboard backtest  (policy={risk_mode})  {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
                 fontsize=12, fontweight="bold", y=0.98)

    # Grille 2 rangées: TOP table (haut), Heatmap (bas)
    gs = fig.add_gridspec(2, 1, height_ratios=[1.2, 1.8], hspace=0.25)

    # --- TOP K table
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.axis("off")
    if df_top.empty:
        ax1.text(0.5, 0.5, "Aucun résultat TOP.", ha="center", va="center", fontsize=12)
    else:
        tbl = ax1.table(cellText=df_top.values,
                        colLabels=df_top.columns.tolist(),
                        loc="center", cellLoc="center")
        tbl.scale(1, 1.3)
        for (row, col), cell in tbl.get_celld().items():
            if row == 0:
                cell.set_facecolor("#1f2937"); cell.set_text_props(color="white", weight="bold")
            else:
                cell.set_facecolor("#ffffff")
        ax1.set_title(f"TOP {min(TOP_K, len(df_top))}", loc="left", fontsize=11, pad=8)

    # --- Heatmap PF
    ax2 = fig.add_subplot(gs[1, 0])
    if heat.empty:
        ax2.axis("off")
        ax2.text(0.5, 0.5, "Pas de données pour la heatmap PF.", ha="center", va="center", fontsize=12)
    else:
        sns.heatmap(heat, ax=ax2, cmap="RdYlGn", annot=True, fmt=".2f",
                    cbar_kws={"label":"PF"}, linewidths=0.5, linecolor="#e5e7eb")
        ax2.set_xlabel("TF"); ax2.set_ylabel("PAIR")
        ax2.set_title("PF max par paire × TF", fontsize=11)

    fig.savefig(OUT_PNG, bbox_inches="tight")
    _log(f"PNG écrit → {OUT_PNG}")

def _draw_pdf(pd, OUT_PDF):
    # PDF = convertir l'image PNG en PDF (via reportlab) pour iPhone
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader
        from PIL import Image
    except Exception:
        # fallback: rien
        _log("reportlab/PIL absents — PDF non généré (PNG OK).")
        return
    try:
        img = Image.open(OUT_PNG)
        w, h = img.size
        page_w, page_h = A4
        scale = min(page_w / w, page_h / h)
        pdf = canvas.Canvas(OUT_PDF, pagesize=A4)
        pdf.drawImage(ImageReader(img), x=0, y=0, width=w*scale, height=h*scale, preserveAspectRatio=True, anchor='sw')
        pdf.showPage(); pdf.save()
        _log(f"PDF écrit → {OUT_PDF}")
    except Exception as e:
        _log(f"PDF échec: {e}")

def generate():
    _ensure_libs()

    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    # données
    sm = _load_json(SUMMARY)
    rows = sm.get("rows", [])
    risk_mode = sm.get("risk_mode", "normal")

    rows_sorted = sorted(rows, key=_score, reverse=True)
    df_top, heat = _build_tables(pd, rows_sorted)

    # rendu
    _draw_png(pd, plt, sns, df_top, heat, risk_mode)
    _draw_pdf(pd, OUT_PDF)

if __name__ == "__main__":
    try:
        generate()
    except Exception as e:
        _log(f"erreur fatale: {e}")
        sys.exit(1)