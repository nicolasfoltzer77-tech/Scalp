#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCALP — Génère le dashboard HTML (+ auto-refresh) dans /docs
puis déclenche la publication GitHub Pages via:  python -m tools.publish_pages

- Lit (si présents) : engine/config/config.yaml, reports/status.json,
  reports/summary.json, reports/last_errors.json
- Écrit : docs/index.html et docs/dashboard.html
- N'échoue pas si la publication GitHub échoue (log et continue)
"""

from __future__ import annotations
import os
import sys
import json
import time
import subprocess
from pathlib import Path
from typing import Any, Dict

# ------------------------------------------------------------
# Réglages
# ------------------------------------------------------------
AUTO_REFRESH_SECS = int(os.environ.get("AUTO_REFRESH_SECS", "5"))  # meta refresh

# ------------------------------------------------------------
# Chemins
# ------------------------------------------------------------
REPO_ROOT: Path = Path(__file__).resolve().parents[1]   # <repo>
DOCS_DIR: Path  = REPO_ROOT / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)

CFG_PATH: Path  = REPO_ROOT / "engine" / "config" / "config.yaml"

# ------------------------------------------------------------
# Helpers IO
# ------------------------------------------------------------
def load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        import yaml
    except Exception:
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def now_utc_str() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + " UTC"

def guess_reports_dir() -> Path:
    cfg = load_yaml(CFG_PATH)
    rt  = cfg.get("runtime", {}) if isinstance(cfg, dict) else {}
    v   = rt.get("reports_dir")
    if isinstance(v, str) and v.strip():
        return Path(v)
    # fallbacks usuels
    cands = [
        Path("/notebooks/scalp_data/reports"),
        REPO_ROOT / "scalp_data" / "reports",
    ]
    for p in cands:
        if p.exists():
            return p
    return cands[0]

REPORTS_DIR: Path = guess_reports_dir()

# ------------------------------------------------------------
# Rendu HTML
# ------------------------------------------------------------
def _badge(label: str, val, color: str) -> str:
    return (f"<span style='display:inline-block;margin:4px 8px;padding:4px 10px;"
            f"border-radius:14px;background:{color};color:#fff;font-weight:600'>"
            f"{label}: {val}</span>")

def render_html(cfg: Dict[str, Any], status: Dict[str, Any],
                summary: Dict[str, Any], last: Dict[str, Any]) -> str:
    rt = (cfg.get("runtime") or {}) if isinstance(cfg, dict) else {}
    risk_mode = (rt.get("risk_mode") or "normal").lower()
    tf_list   = list(rt.get("tf_list", ["1m","5m","15m"]))

    counts = status.get("counts", {}) or {}
    matrix = status.get("matrix", []) or []
    rows   = summary.get("rows", []) or []

    # tri simple du TOP 20
    rows_sorted = sorted(
        rows,
        key=lambda r: (r.get("pf",0)*2 + r.get("sharpe",0)*0.5 + r.get("wr",0)*0.5 - r.get("mdd",1)*1.5),
        reverse=True
    )[:20]

    H: list[str] = []
    H.append("<!doctype html>")
    H.append("<meta charset='utf-8'>")
    H.append("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    H.append(f"<meta http-equiv='refresh' content='{AUTO_REFRESH_SECS}'>")  # auto-refresh
    H.append("<title>SCALP — Dashboard</title>")
    H.append("""
    <style>
      body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:24px;color:#111}
      h1{font-size:32px;margin:0 0 12px} h2{margin:0 0 10px}
      .card{border:1px solid #e8e8e8;border-radius:10px;padding:16px 18px;margin:18px 0}
      table{border-collapse:collapse;width:100%} th,td{border:1px solid #eee;padding:6px 8px;text-align:left}
      th{background:#fafafa}
      .MIS{color:#666;font-weight:700}.OLD{color:#d90000;font-weight:700}
      .DAT{color:#b88600;font-weight:700}.OK{color:#0a910a;font-weight:700}
      small{color:#6b7280}.muted{color:#6b7280;font-size:12px}
      .mono{font-family:ui-monospace,Menlo,Consolas,monospace}
    </style>
    """)
    H.append(f"<h1>SCALP — Dashboard <small>({now_utc_str()})</small></h1>")
    H.append(f"<div class='muted'>Auto-refresh: {AUTO_REFRESH_SECS}s · risk_mode: {risk_mode}</div>")

    # Statut data
    H.append('<div class="card"><h2>Statut des données (pair × TF)</h2>')
    H.append(_badge("MIS", counts.get("MIS",0), "#6b7280"))
    H.append(_badge("OLD", counts.get("OLD",0), "#d90000"))
    H.append(_badge("DAT", counts.get("DAT",0), "#b88600"))
    H.append(_badge("OK",  counts.get("OK",0),  "#0a910a"))
    if matrix:
        H.append("<div style='height:8px'></div>")
        H.append("<table><thead><tr><th>PAIR</th>"+ "".join(f"<th>{tf}</th>" for tf in tf_list) +"</tr></thead><tbody>")
        for row in matrix:
            H.append("<tr><td><b>{}</b></td>{}</tr>".format(
                row.get("pair","?"),
                "".join(f"<td class='{row.get(tf,'MIS')}'>{row.get(tf,'MIS')}</td>" for tf in tf_list)
            ))
        H.append("</tbody></table>")
    else:
        H.append("<div>Aucune matrice (status.json manquant ou vide).</div>")
    H.append("</div>")

    # TOP 20
    H.append(f'<div class="card"><h2>TOP 20 (policy={risk_mode})</h2>')
    if rows_sorted:
        H.append("<table><thead><tr><th>#</th><th>PAIR</th><th>TF</th><th>PF</th><th>MDD</th><th>TR</th><th>WR</th><th>Sharpe</th></tr></thead><tbody>")
        for i, r in enumerate(rows_sorted, 1):
            H.append(f"<tr><td>{i}</td><td>{r.get('pair')}</td><td>{r.get('tf')}</td>"
                     f"<td>{r.get('pf',0):.3f}</td><td>{r.get('mdd',0):.1%}</td><td>{r.get('trades',0)}</td>"
                     f"<td>{r.get('wr',0):.1%}</td><td>{r.get('sharpe',0):.2f}</td></tr>")
        H.append("</tbody></table>")
    else:
        H.append("<div>Aucun résultat TOP.</div>")
    H.append("</div>")

    # Dernières actions
    H.append('<div class="card"><h2>Dernières actions</h2>')
    if last:
        H.append("<pre class='mono' style='white-space:pre-wrap;background:#fafafa;padding:10px;border-radius:8px;border:1px solid #eee'>")
        H.append(json.dumps(last, ensure_ascii=False, indent=2))
        H.append("</pre>")
    else:
        H.append("<div>Aucune info (last_errors.json manquant).</div>")
    H.append("</div>")

    # Cache-buster pour liens internes éventuels
    H.append("""
    <script>
      (function(){
        const stamp = Date.now();
        document.querySelectorAll("a[href]").forEach(a=>{
          try{const u=new URL(a.href,location.href);u.searchParams.set("_t",stamp);a.href=u}catch(e){}
        });
      })();
    </script>
    """)
    return "\n".join(H)

# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def main():
    # 1) cfg minimale (si besoin on pourra la peupler)
    cfg = load_yaml(CFG_PATH)

    # 2) lire data
    status  = load_json(REPORTS_DIR / "status.json")
    summary = load_json(REPORTS_DIR / "summary.json")
    last    = load_json(REPORTS_DIR / "last_errors.json")

    # 3) render
    html = render_html(cfg, status, summary, last)

    # 4) écrire /docs
    index_path = DOCS_DIR / "index.html"
    dash_path  = DOCS_DIR / "dashboard.html"
    index_path.write_text(html, encoding="utf-8")
    dash_path.write_text(html,  encoding="utf-8")
    print(f"[render] Dashboard écrit → {index_path}")

    # 5) publication GitHub Pages (via module dédié, évite soucis d'import)
    try:
        subprocess.run(
            [sys.executable, "-m", "tools.publish_pages"],
            cwd=str(REPO_ROOT),
            check=True
        )
    except Exception as e:
        print(f"[render] publication GitHub Pages ignorée: {e}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[render] FATAL: {e}")
        sys.exit(1)