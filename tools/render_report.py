#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import os, json, time, yaml

# --- Réglage auto-refresh (en secondes) ---
AUTO_REFRESH_SECS = 2  # tu peux passer à 3/10/etc.

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CFG_PATH   = os.path.join(REPO_ROOT, "engine", "config", "config.yaml")

def load_yaml(p, missing_ok=False):
    if missing_ok and not os.path.isfile(p): return {}
    with open(p, "r", encoding="utf-8") as f: return yaml.safe_load(f) or {}

def load_json(p, missing_ok=False):
    if missing_ok and not os.path.isfile(p): return {}
    with open(p, "r", encoding="utf-8") as f: return json.load(f)

def now_utc_str():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + " UTC"

def badge(label, val, color):
    return f"""<span style="display:inline-block;margin:4px 8px;padding:4px 10px;border-radius:14px;background:{color};color:#fff;font-weight:600;">{label}: {val}</span>"""

def render():
    cfg = load_yaml(CFG_PATH, missing_ok=True)
    rt = cfg.get("runtime", {}) if isinstance(cfg, dict) else {}
    reports_dir = rt.get("reports_dir", "/notebooks/scalp_data/reports")
    risk_mode   = (rt.get("risk_mode") or "normal").lower()

    summary = load_json(os.path.join(reports_dir, "summary.json"), missing_ok=True) or {"rows":[],"meta":{}}
    status  = load_json(os.path.join(reports_dir, "status.json"),  missing_ok=True) or {"counts":{},"matrix":[]}
    last    = load_json(os.path.join(reports_dir, "last_errors.json"), missing_ok=True) or {}

    counts   = status.get("counts", {})
    matrix   = status.get("matrix", [])
    tf_list  = list(rt.get("tf_list", ["1m","5m","15m"]))
    rows     = summary.get("rows", [])
    rows_sorted = sorted(
        rows,
        key=lambda r: (r.get("pf",0)*2 + r.get("sharpe",0)*0.5 + r.get("wr",0)*0.5 - r.get("mdd",1)*1.5),
        reverse=True
    )[:20]

    # HTML
    html = []
    html.append("<!doctype html>")
    html.append("<meta charset='utf-8'>")
    # Auto-refresh hard (meta) + cache-buster JS (soft)
    html.append(f"<meta http-equiv='refresh' content='{AUTO_REFRESH_SECS}'>")
    html.append("<title>SCALP — Dashboard</title>")
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
      .muted { color:#6b7280; font-size:12px; }
    </style>
    """)
    html.append(f"<h1>SCALP — Dashboard <small>({now_utc_str()})</small></h1>")
    html.append(f"<div class='muted'>Auto-refresh: {AUTO_REFRESH_SECS}s · risk_mode: {risk_mode}</div>")

    # === STATUT DATA ===
    html.append('<div class="card"><h2>Statut des données (pair × TF)</h2>')
    html.append(badge("MIS", counts.get("MIS",0), "#6b7280"))
    html.append(badge("OLD", counts.get("OLD",0), "#d90000"))
    html.append(badge("DAT", counts.get("DAT",0), "#b88600"))
    html.append(badge("OK",  counts.get("OK",0),  "#0a910a"))
    if matrix:
        html.append("<div style='height:8px'></div>")
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
    html.append(f'<div class="card"><h2>TOP 20 (policy={risk_mode})</h2>')
    if rows_sorted:
        html.append("<table><thead><tr><th>#</th><th>PAIR</th><th>TF</th><th>PF</th><th>MDD</th><th>TR</th><th>WR</th><th>Sharpe</th></tr></thead><tbody>")
        for i, r in enumerate(rows_sorted, 1):
            html.append(f"<tr><td>{i}</td><td>{r['pair']}</td><td>{r['tf']}</td>"
                        f"<td>{r['pf']:.3f}</td><td>{r['mdd']:.1%}</td><td>{r['trades']}</td>"
                        f"<td>{r['wr']:.1%}</td><td>{r['sharpe']:.2f}</td></tr>")
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

    # JS cache-buster (si navigation via lien)
    html.append("""
    <script>
      // Ajoute un cache-buster si l'utilisateur navigue via des liens internes
      (function(){
        const links = document.querySelectorAll("a[href]");
        const stamp = Date.now();
        links.forEach(a => {
          try {
            const u = new URL(a.href, window.location.href);
            u.searchParams.set("_t", stamp);
            a.href = u.toString();
          } catch(e){}
        });
      })();
    </script>
    """)

    return "\n".join(html)

def main():
    out = os.path.join(REPO_ROOT, "dashboard.html")  # à la racine
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(render())
    print(f"[render] Dashboard écrit → {out}")

if __name__ == "__main__":
    main()