#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Render dashboard + publication GitHub Pages.

- Lit engine/config/config.yaml pour localiser reports_dir
- Consomme reports/{status.json, summary.json, last_errors.json}
- Génère un HTML avec auto-refresh (meta) + cache-buster JS
- Écrit dans docs/index.html (+ docs/dashboard.html)
- Fait git add/commit/push (sécurisé) :
  * Si GH_TOKEN + GH_REPO: configure/force remote origin HTTPS avec token
  * Sinon: utilise remote 'origin' déjà configuré
  * Si rien n’est configuré: log et n’échoue pas

Variables d’environnement utiles :
- AUTO_REFRESH_SECS (défaut 5)
- GH_TOKEN (facultatif, PAT GitHub)
- GH_REPO  (facultatif, ex: "monuser/scalp")
"""

from __future__ import annotations
import os, sys, json, time, subprocess
from pathlib import Path
from typing import Dict, Any

try:
    import yaml
except ImportError:
    # yaml peut manquer au tout premier run : fallback simple
    yaml = None

# ---------- Réglages ----------
AUTO_REFRESH_SECS = int(os.environ.get("AUTO_REFRESH_SECS", "5"))

# ---------- Arborescence ----------
REPO_ROOT = Path(__file__).resolve().parents[1]   # <repo>/tools/.. => <repo>
CFG_PATH  = REPO_ROOT / "engine" / "config" / "config.yaml"
DOCS_DIR  = REPO_ROOT / "docs"                    # GitHub Pages sert /docs
DOCS_DIR.mkdir(parents=True, exist_ok=True)

# ---------- Helpers I/O ----------
def load_yaml(path: Path, missing_ok: bool = False) -> Dict[str, Any]:
    if missing_ok and not path.exists():
        return {}
    if yaml is None:
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def load_json(path: Path, missing_ok: bool = False) -> Dict[str, Any]:
    if missing_ok and not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def now_utc_str() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + " UTC"

def badge(label: str, val: Any, color: str) -> str:
    return (
        f"<span style='display:inline-block;margin:4px 8px;"
        f"padding:4px 10px;border-radius:14px;background:{color};"
        f"color:#fff;font-weight:600;'>{label}: {val}</span>"
    )

# ---------- Rendu HTML ----------
def render_html(cfg: Dict[str, Any], status: Dict[str, Any], summary: Dict[str, Any], last: Dict[str, Any]) -> str:
    rt = cfg.get("runtime", {}) if isinstance(cfg, dict) else {}
    risk_mode = (rt.get("risk_mode") or "normal").lower()
    tf_list   = list(rt.get("tf_list", ["1m","5m","15m"]))

    counts = status.get("counts", {}) or {}
    matrix = status.get("matrix", []) or []

    rows = (summary or {}).get("rows", []) or []
    rows_sorted = sorted(
        rows,
        key=lambda r: (r.get("pf",0)*2 + r.get("sharpe",0)*0.5 + r.get("wr",0)*0.5 - r.get("mdd",1)*1.5),
        reverse=True
    )[:20]

    html = []
    html.append("<!doctype html>")
    html.append("<meta charset='utf-8'>")
    html.append(f"<meta http-equiv='refresh' content='{AUTO_REFRESH_SECS}'>")
    html.append("<meta name='viewport' content='width=device-width, initial-scale=1.0'>")
    html.append("<title>SCALP — Dashboard</title>")
    html.append("""
    <style>
      body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; color:#111;}
      h1 { font-size: 32px; margin: 0 0 12px 0;}
      h2 { margin: 0 0 10px 0; }
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
      .grid { display:grid; grid-template-columns: 1fr; gap: 16px; }
      @media (min-width: 900px) { .grid { grid-template-columns: 1fr 1fr; } }
      .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    </style>
    """)
    html.append(f"<h1>SCALP — Dashboard <small>({now_utc_str()})</small></h1>")
    html.append(f"<div class='muted'>Auto-refresh: {AUTO_REFRESH_SECS}s · risk_mode: {risk_mode}</div>")

    # --- STATUT ---
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

    # --- TOP 20 ---
    html.append(f'<div class="card"><h2>TOP 20 (policy={risk_mode})</h2>')
    if rows_sorted:
        html.append("<table><thead><tr><th>#</th><th>PAIR</th><th>TF</th><th>PF</th><th>MDD</th><th>TR</th><th>WR</th><th>Sharpe</th></tr></thead><tbody>")
        for i, r in enumerate(rows_sorted, 1):
            html.append(
                f"<tr><td>{i}</td><td>{r['pair']}</td><td>{r['tf']}</td>"
                f"<td>{r['pf']:.3f}</td><td>{r['mdd']:.1%}</td><td>{r['trades']}</td>"
                f"<td>{r['wr']:.1%}</td><td>{r['sharpe']:.2f}</td></tr>"
            )
        html.append("</tbody></table>")
    else:
        html.append("<div>Aucun résultat TOP.</div>")
    html.append("</div>")

    # --- Dernières actions ---
    html.append('<div class="card"><h2>Dernières actions</h2>')
    if last:
        html.append("<pre class='mono' style='white-space:pre-wrap;background:#fafafa;padding:10px;border-radius:8px;border:1px solid #eee;'>")
        html.append(json.dumps(last, ensure_ascii=False, indent=2))
        html.append("</pre>")
    else:
        html.append("<div>Aucune info (last_errors.json manquant).</div>")
    html.append("</div>")

    # Cache-buster JS pour liens internes (si tu en ajoutes un jour)
    html.append("""
    <script>
      (function(){
        const links = document.querySelectorAll("a[href]");
        const stamp = Date.now();
        links.forEach(a => {
          try { const u = new URL(a.href, window.location.href);
                u.searchParams.set("_t", stamp); a.href = u.toString(); } catch(e){}
        });
      })();
    </script>
    """)

    return "\n".join(html)

# ---------- Git helpers ----------
def _git(*args, check=True):
    return subprocess.run(["git", *args], cwd=str(REPO_ROOT), capture_output=True, text=True, check=check)

def _ensure_git_identity():
    try:
        _git("config", "user.email")
    except subprocess.CalledProcessError:
        _git("config", "user.email", "bot@local")
    try:
        _git("config", "user.name")
    except subprocess.CalledProcessError:
        _git("config", "user.name", "SCALP Bot")

def _maybe_set_remote_with_token():
    token = os.environ.get("GH_TOKEN", "").strip()
    gh_repo = os.environ.get("GH_REPO", "").strip()  # ex: "monuser/scalp"
    if not token or not gh_repo:
        return False
    url = f"https://x-access-token:{token}@github.com/{gh_repo}.git"
    try:
        remotes = _git("remote").stdout.strip().splitlines()
        if "origin" not in remotes:
            _git("remote", "add", "origin", url)
        else:
            _git("remote", "set-url", "origin", url)
        return True
    except subprocess.CalledProcessError:
        return False

def git_publish(paths_to_add):
    # Dans un repo ?
    try:
        _git("rev-parse", "--is-inside-work-tree")
    except subprocess.CalledProcessError:
        print("[render] (git) pas un dépôt git : push ignoré.")
        return

    _ensure_git_identity()
    for p in paths_to_add:
        try:
            _git("add", str(p))
        except subprocess.CalledProcessError as e:
            print("[render] (git add) erreur:", e.stderr.strip())

    # commit seulement s'il y a des changements
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=str(REPO_ROOT))
    if diff.returncode == 0:
        print("[render] Aucun changement à committer.")
        return

    try:
        _git("commit", "-m", f"pages: update at {now_utc_str()}")
    except subprocess.CalledProcessError as e:
        print("[render] (git commit) erreur:", e.stderr.strip())
        return

    # Remote avec token si dispo, sinon on garde origin tel quel
    _maybe_set_remote_with_token()

    try:
        _git("push", "origin", "HEAD:main")
        print("[render] ✅ Poussé sur GitHub (origin main).")
    except subprocess.CalledProcessError as e:
        print("[render] ⚠️ Push échoué:", e.stderr.strip())

# ---------- Main ----------
def main():
    # 1) charger config → chemins
    cfg = load_yaml(CFG_PATH, missing_ok=True)
    rt  = cfg.get("runtime", {}) if isinstance(cfg, dict) else {}
    reports_dir = Path(rt.get("reports_dir", "/notebooks/scalp_data/reports"))

    # 2) lire data
    status  = load_json(reports_dir / "status.json",      missing_ok=True) or {}
    summary = load_json(reports_dir / "summary.json",     missing_ok=True) or {}
    last    = load_json(reports_dir / "last_errors.json", missing_ok=True) or {}

    # 3) render
    html = render_html(cfg, status, summary, last)

    # 4) écrire vers Pages
    index_path = DOCS_DIR / "index.html"       # page servie par défaut
    dash_path  = DOCS_DIR / "dashboard.html"   # copie optionnelle
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    index_path.write_text(html, encoding="utf-8")
    dash_path.write_text(html,  encoding="utf-8")
    print(f"[render] Dashboard écrit → {index_path}")

    # 5) publier (git)
    git_publish([index_path, dash_path])

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[render] FATAL: {e}")
        sys.exit(1)