#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCALP — Génère le dashboard HTML + auto-refresh,
écrit dans /docs/index.html et /docs/dashboard.html,
puis déclenche la publication GitHub Pages (tools.publish_pages).
"""

from __future__ import annotations
import os, sys, json, time
from pathlib import Path

# ---------- Réglages ----------
AUTO_REFRESH_SECS = int(os.environ.get("AUTO_REFRESH_SECS", "5"))  # auto-refresh HTML

# ---------- Chemins ----------
REPO_ROOT = Path(__file__).resolve().parents[1]         # <repo>
DOCS_DIR  = REPO_ROOT / "docs"                           # Pages sert /docs
DOCS_DIR.mkdir(parents=True, exist_ok=True)

# reports_dir: on tente engine/config/config.yaml, sinon fallback standard
def _guess_reports_dir() -> Path:
    cfg_p = REPO_ROOT / "engine" / "config" / "config.yaml"
    try:
        import yaml  # léger
        if cfg_p.exists():
            rt = yaml.safe_load(cfg_p.read_text(encoding="utf-8")) or {}
            rt = (rt or {}).get("runtime", {})
            if isinstance(rt, dict) and rt.get("reports_dir"):
                return Path(rt["reports_dir"])
    except Exception:
        pass
    # fallback simple
    return Path("/notebooks/scalp_data/reports")

REPORTS_DIR = _guess_reports_dir()

# ---------- IO util ----------
def load_json(p: Path, missing_ok: bool = True):
    if missing_ok and not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

def now_utc_str() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + " UTC"

def _badge(label: str, val, color: str) -> str:
    return (f"<span style='display:inline-block;margin:4px 8px;padding:4px 10px;"
            f"border-radius:14px;background:{color};color:#fff;font-weight:600;'>"
            f"{label}: {val}</span>")

# ---------- Rendu HTML (auto-refresh inclus) ----------
def render_html(cfg: dict, status: dict, summary: dict, last: dict) -> str:
    rt = (cfg.get("runtime") or {}) if isinstance(cfg, dict) else {}
    risk_mode = (rt.get("risk_mode") or "normal").lower()
    tf_list   = list(rt.get("tf_list", ["1m","5m","15m"]))

    counts = status.get("counts", {}) or {}
    matrix = status.get("matrix", []) or []
    rows   = summary.get("rows", []) or []

    rows_sorted = sorted(
        rows,
        key=lambda r: (r.get("pf",0)*2 + r.get("sharpe",0)*0.5 + r.get("wr",0)*0.5 - r.get("mdd",1)*1.5),
        reverse=True
    )[:20]

    H = []
    H.append("<!doctype html>")
    H.append("<meta charset='utf-8'>")
    H.append("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    H.append(f"<meta http-equiv='refresh' content='{AUTO_REFRESH_SECS}'>")  # << auto-refresh
    H.append("<title>SCALP — Dashboard</title>")
    H.append("""
    <style>
      body { font-family: system-ui,-apple-system,Segoe UI,Roboto,sans-serif; margin:24px; color:#111;}
      h1 { font-size:32px; margin:0 0 12px 0;}
      h2 { margin:0 0 10px 0;}
      .card { border:1px solid #e8e8e8; border-radius:10px; padding:16px 18px; margin:18px 0;}
      table { border-collapse: collapse; width:100%;}
      th,td { border:1px solid #eee; padding:6px 8px; text-align:left;}
      th { background:#fafafa;}
      .MIS{color:#666;font-weight:700;} .OLD{color:#d90000;font-weight:700;}
      .DAT{color:#b88600;font-weight:700;} .OK{color:#0a910a;font-weight:700;}
      small{color:#6b7280;} .muted{color:#6b7280;font-size:12px;}
      .mono{font-family:ui-monospace,Menlo,Consolas,monospace;}
    </style>
    """)
    H.append(f"<h1>SCALP — Dashboard <small>({now_utc_str()})</small></h1>")
    H.append(f"<div class='muted'>Auto-refresh: {AUTO_REFRESH_SECS}s · risk_mode: {risk_mode}</div>")

    # --- Statut data ---
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

    # --- TOP 20 ---
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

    # --- Dernières actions ---
    H.append('<div class="card"><h2>Dernières actions</h2>')
    if last:
        H.append("<pre class='mono' style='white-space:pre-wrap;background:#fafafa;padding:10px;border-radius:8px;border:1px solid #eee;'>")
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
          try{ const u=new URL(a.href,location.href); u.searchParams.set("_t",stamp); a.href=u; }catch(e){}
        });
      })();
    </script>""")

    return "\n".join(H)

# ---------- Main ----------
def main():
    # cfg minimal (si tu veux, tu peux y copier la conf)
    cfg = {"runtime": {}}  # on garde léger

    # lire data
    status  = load_json(REPORTS_DIR / "status.json")
    summary = load_json(REPORTS_DIR / "summary.json")
    last    = load_json(REPORTS_DIR / "last_errors.json")

    # render
    html = render_html(cfg, status, summary, last)

    # écrire /docs
    index_path = DOCS_DIR / "index.html"
    dash_path  = DOCS_DIR / "dashboard.html"
    index_path.write_text(html, encoding="utf-8")
    dash_path.write_text(html,  encoding="utf-8")
    print(f"[render] Dashboard écrit → {index_path}")

    # publier (git) : passe par l’outil dédié (robuste, copies JSON)
    try:
        from tools.publish_pages import main as publish_pages_main
        publish_pages_main()
    except Exception as e:
        print(f"[render] publication GitHub Pages ignorée: {e}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[render] FATAL: {e}")
        sys.exit(1)