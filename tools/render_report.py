#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
tools/render_report.py

Génère un dashboard statique (index.html) dans <REPO_PATH>/docs/
+ push automatique vers GitHub Pages (via tools.publish_pages).

Points clés:
- Auto-refresh 5 s (compte à rebours + bouton "Refresh")
- Cartes "Health" / "Compteurs" avec placeholders si pas de data
- Heatmap PF pair × TF (Plotly), sinon placeholder graphique
- TOP résultats avec filtre pair/TF côté client
- Lecture des JSON depuis <REPO_PATH>/reports/
- Copie/push des artefacts vers /docs/ via publish_pages

ENV utiles:
  REPO_PATH=/notebooks/scalp         # défaut
  GIT_USER / GIT_TOKEN / GIT_REPO    # pour publish_pages
"""

from __future__ import annotations
import json, os, sys, time, traceback
from pathlib import Path
from datetime import datetime, timezone

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

REPO_PATH = Path(os.environ.get("REPO_PATH", "/notebooks/scalp")).resolve()
DOCS_DIR  = REPO_PATH / "docs"
DATA_DIR  = DOCS_DIR / "data"
REPORTS_DIR = REPO_PATH / "reports"
DOCS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

def _load_json(p: Path):
    try:
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def _ts_utc_now() -> int:
    return int(time.time())

def _ts_to_iso_utc(ts: int | float | None) -> str:
    if not ts:
        return "—"
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def _age_human(ts: int | float | None) -> str:
    if not ts:
        return "n/a"
    delta = max(0, _ts_utc_now() - int(ts))
    if delta < 60:
        return f"{delta}s"
    if delta < 3600:
        m = delta // 60
        return f"{m} min"
    h = delta // 3600
    return f"{h} h"

def _safe_get(d: dict | None, *keys, default=None):
    cur = d or {}
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default

# -----------------------------------------------------------------------------
# Lecture données
# -----------------------------------------------------------------------------

def read_inputs():
    # status.json: photo MIS/OLD/DAT/OK
    status = _load_json(REPORTS_DIR / "status.json") or {}
    # summary.json: résumé backtest (top, heatmap, etc.)
    summary = _load_json(REPORTS_DIR / "summary.json") or {}
    # health.json: généré au publish
    health = _load_json(DOCS_DIR / "health.json") or {}

    # Compteurs
    counts = {
        "MIS": int(_safe_get(status, "counts", "MIS", default=0) or 0),
        "OLD": int(_safe_get(status, "counts", "OLD", default=0) or 0),
        "DAT": int(_safe_get(status, "counts", "DAT", default=0) or 0),
        "OK":  int(_safe_get(status, "counts", "OK",  default=0) or 0),
    }
    # Fraîcheur (pour la bannière)
    generated_at = _safe_get(summary, "generated_at", default=None)
    risk_mode    = _safe_get(summary, "risk_mode", default="n/a")
    walkf        = _safe_get(summary, "meta", "walk_forward", default={})
    opti         = _safe_get(summary, "meta", "optuna", default={})
    rows         = _safe_get(summary, "rows", default=[]) or []

    # Pour heatmap: on attend des lignes avec pair, tf, pf
    heat_rows = []
    for r in rows:
        pair = r.get("pair") or r.get("symbol") or r.get("pair_tf", "").split(":")[0]
        tf   = r.get("tf")   or (r.get("pair_tf", "").split(":")[1] if ":" in r.get("pair_tf","") else None)
        pf   = r.get("metrics", {}).get("pf") or r.get("pf")
        if pair and tf and pf is not None:
            try:
                heat_rows.append((pair, tf, float(pf)))
            except Exception:
                pass

    # Liste pairs / tfs pour filtre TOP
    pairs = sorted({p for p, _, _ in heat_rows}) if heat_rows else sorted({r.get("pair") for r in rows if r.get("pair")})
    tfs   = sorted({t for _, t, _ in heat_rows}) if heat_rows else sorted({r.get("tf") for r in rows if r.get("tf")})

    payload = {
        "status": status,
        "summary": summary,
        "health": health,
        "counts": counts,
        "rows": rows,
        "heat_rows": heat_rows,
        "pairs": [p for p in pairs if p],
        "tfs":   [t for t in tfs   if t],
        "generated_at": generated_at,
        "risk_mode": risk_mode,
        "walk_forward": walkf,
        "optuna": opti,
    }
    return payload

# -----------------------------------------------------------------------------
# Rendu HTML
# -----------------------------------------------------------------------------

PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.27.0.min.js"

def render_html(data: dict) -> str:
    counts = data["counts"]
    rows   = data["rows"]
    heat   = data["heat_rows"]
    pairs  = data["pairs"]
    tfs    = data["tfs"]

    now_iso = _ts_to_iso_utc(_ts_utc_now())
    gen_iso = _ts_to_iso_utc(data.get("generated_at"))
    gen_age = _age_human(data.get("generated_at"))

    # prépare données heatmap pour JS
    # on crée un dict {pair: {tf: pf}}
    heat_map = {}
    for p, tf, pf in heat:
        heat_map.setdefault(p, {})[tf] = pf

    # Top K (limité pour lisibilité)
    # score par défaut: PF desc, WR desc, -MDD
    def _score(r):
        m = r.get("metrics", {})
        pf   = m.get("pf") or 0.0
        wr   = m.get("wr") or 0.0
        mdd  = m.get("mdd") or 0.0
        # simple score
        return (float(pf), float(wr), -float(mdd))

    top_rows = sorted(rows, key=_score, reverse=True)[:50]

    # JS: on injecte heat_map, pairs, tfs, et top_rows pour filtres client
    def js_json_safe(obj):
        return json.dumps(obj, ensure_ascii=False)

    html = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>SCALP — Dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="{PLOTLY_CDN}"></script>
<style>
  :root {{
    --bg:#0b0f14; --card:#121820; --text:#e6edf3; --muted:#9aa6b2;
    --ok:#2aa745; --dat:#c89d28; --old:#d0443e; --mis:#7b8a97; --chip:#1f2937;
    --accent:#3b82f6; --border:#223040;
  }}
  html,body {{ background:var(--bg); color:var(--text); font:16px/1.45 system-ui, -apple-system, Segoe UI, Roboto, Arial; margin:0; padding:0; }}
  .wrap {{ max-width:1100px; margin:0 auto; padding:20px; }}
  h1 {{ font-size:2.1rem; margin:10px 0 8px; }}
  small.muted {{ color:var(--muted); }}
  .row {{ display:grid; grid-template-columns: 1fr; gap:16px; }}
  @media (min-width: 900px) {{
    .row-2 {{ grid-template-columns: 1fr 1fr; }}
  }}
  .card {{ background:var(--card); border:1px solid var(--border); border-radius:10px; padding:18px; }}
  .title {{ font-size:1.25rem; margin:0 0 10px; }}
  .chips span {{ display:inline-block; background:var(--chip); padding:6px 10px; border-radius:999px; margin-right:8px; font-weight:600; }}
  .chips .mis {{ background:var(--mis); color:#081217; }}
  .chips .old {{ background:var(--old); color:#fff; }}
  .chips .dat {{ background:var(--dat); color:#0b0f14; }}
  .chips .ok  {{ background:var(--ok);  color:#0b0f14; }}
  .muted {{ color:var(--muted); }}
  .flex {{ display:flex; align-items:center; gap:12px; flex-wrap:wrap; }}
  button.refresh {{ background:var(--accent); color:white; border:0; padding:6px 12px; border-radius:8px; cursor:pointer; }}
  table {{ width:100%; border-collapse:collapse; }}
  th,td {{ padding:8px 10px; border-bottom:1px solid var(--border); }}
  th {{ text-align:left; color:var(--muted); font-weight:600; }}
  tr:hover td {{ background:#0f141c; }}
  .right {{ text-align:right; }}
  .placeholder {{ border:1px dashed var(--border); color:var(--muted); padding:18px; border-radius:10px; }}
  .badge {{ padding:3px 8px; border-radius:6px; font-weight:700; }}
  .badge.ok  {{ background:var(--ok);  color:#0b0f14; }}
  .badge.dat {{ background:var(--dat); color:#0b0f14; }}
  .badge.old {{ background:var(--old); color:#fff;    }}
  .badge.mis {{ background:var(--mis); color:#081217;}}
</style>
</head>
<body>
<div class="wrap">
  <h1>SCALP — Dashboard <small class="muted">({now_iso})</small></h1>
  <div class="flex" style="margin:6px 0 18px;">
    <div class="muted">Auto-refresh: <b id="rf-interval">5s</b> · reload dans <span id="rf-count">5</span>s</div>
    <button class="refresh" onclick="location.reload()">Refresh</button>
  </div>

  <div class="row row-2">
    <div class="card">
      <div class="title">Health</div>
      <div id="health">
        <div><span class="muted">generated_at:</span> <b>{_safe_get(data,'health','generated_at',default='—')}</b></div>
        <div><span class="muted">commit:</span> <b>{_safe_get(data,'health','commit',default='—')}</b></div>
        <div><span class="muted">status:</span> <b style="color:var(--ok);">{_safe_get(data,'health','status',default='pending')}</b></div>
      </div>
    </div>

    <div class="card">
      <div class="title">Compteurs</div>
      <div class="chips">
        <span class="mis">MIS: {counts['MIS']}</span>
        <span class="old">OLD: {counts['OLD']}</span>
        <span class="dat">DAT: {counts['DAT']}</span>
        <span class="ok">OK: {counts['OK']}</span>
      </div>
      <div class="muted" style="margin-top:8px;">
        MIS: no data · OLD: stale · DAT: fresh CSV, no active strategy · OK: fresh CSV + active strategy
      </div>
    </div>
  </div>

  <div class="card" style="margin-top:16px;">
    <div class="title">Heatmap (pair × TF)</div>
    <div id="heat" class="placeholder">Matrice en préparation… en attente des premiers résultats/metrics.</div>
  </div>

  <div class="card" style="margin-top:16px;">
    <div class="title">TOP résultats</div>
    <div class="flex" style="margin-bottom:10px;">
      <label>Pair :
        <select id="f_pair">
          <option value="">(toutes)</option>
          {"".join(f'<option value="{p}">{p}</option>' for p in pairs)}
        </select>
      </label>
      <label>TF :
        <select id="f_tf">
          <option value="">(tous)</option>
          {"".join(f'<option value="{t}">{t}</option>' for t in tfs)}
        </select>
      </label>
    </div>
    <div id="top_table"></div>
  </div>

  <div class="muted" style="margin:20px 0 6px;">
    <small>Dernier backtest: <b>{gen_iso}</b> (age: {gen_age}) · risk_mode: <b>{data.get('risk_mode','n/a')}</b></small>
  </div>
</div>

<script>
  // ---- Auto-refresh 5s
  let left = 5;
  const span = document.getElementById('rf-count');
  setInterval(() => {{
    left = Math.max(0, left-1);
    if (span) span.textContent = left;
    if (left === 0) location.reload();
  }}, 1000);

  // ---- Données injectées (côté client) pour filtres/plot
  const HEAT = {js_json_safe(heat_map)};
  const PAIRS = {js_json_safe(pairs)};
  const TFS = {js_json_safe(tfs)};
  const TOP_ROWS = {js_json_safe(top_rows)};

  // ---- Heatmap Plotly
  function renderHeat() {{
    const el = document.getElementById('heat');
    if (!el) return;
    const pairs = PAIRS;
    const tfs = TFS;
    if (!pairs.length || !tfs.length) {{
      el.className = 'placeholder';
      el.innerText = 'Aucune matrice exploitable (pas encore de PF par pair×TF).';
      return;
    }}
    const z = [];
    for (let i=0;i<pairs.length;i++) {{
      const row = [];
      for (let j=0;j<tfs.length;j++) {{
        const p = pairs[i];
        const tf = tfs[j];
        const v = (HEAT[p] && HEAT[p][tf] != null) ? HEAT[p][tf] : null;
        row.push(v);
      }}
      z.push(row);
    }}
    el.className = '';
    el.innerHTML = '';
    const data = [{{
      z: z, x: tfs, y: pairs, type:'heatmap', colorscale:'Viridis', hoverongaps:false,
      colorbar: {{title:'PF', outlinewidth:0}}
    }}];
    const layout = {{
      paper_bgcolor:'#121820', plot_bgcolor:'#121820',
      font:{{color:'#e6edf3'}},
      margin:{{l:80,r:10,t:10,b:40}}
    }};
    Plotly.newPlot(el, data, layout, {{responsive:true, displayModeBar:false}});
  }}

  // ---- TOP table + filtres
  function number(x, d=2) {{
    if (x===null||x===undefined||isNaN(x)) return '–';
    return Number(x).toFixed(d);
  }}
  function badge(state) {{
    const cls = state || '';
    const val = (state||'').toUpperCase() || '—';
    return `<span class="badge ${cls}">${{val}}</span>`;
  }}
  function renderTop() {{
    const selPair = document.getElementById('f_pair').value;
    const selTf = document.getElementById('f_tf').value;
    let rows = TOP_ROWS.slice();
    if (selPair) rows = rows.filter(r => (r.pair===selPair)||(r.symbol===selPair)||(r.pair_tf||'').startsWith(selPair+':'));
    if (selTf)   rows = rows.filter(r => (r.tf===selTf)||(r.pair_tf||'').endsWith(':'+selTf));
    const head = `
      <table>
        <thead><tr>
          <th>Pair</th><th>TF</th><th>PF</th><th>WR</th><th>MDD</th><th>Trades</th><th>Name</th>
        </tr></thead><tbody>`;
    const body = rows.map(r => {{
      const m = r.metrics||{{}};
      const pair = r.pair || (r.pair_tf||'').split(':')[0] || r.symbol || '—';
      const tf   = r.tf   || (r.pair_tf||'').split(':')[1] || '—';
      return `<tr>
        <td>${{pair}}</td>
        <td>${{tf}}</td>
        <td class="right">${{number(m.pf,2)}}</td>
        <td class="right">${{number(m.wr,2)}}</td>
        <td class="right">${{number(m.mdd,2)}}</td>
        <td class="right">${{m.trades??'–'}}</td>
        <td>${{r.name||'—'}}</td>
      </tr>`;
    }}).join('');
    const tail = `</tbody></table>`;
    document.getElementById('top_table').innerHTML = head + (body || `<div class="placeholder">Aucun résultat pour ce filtre.</div>`) + tail;
  }}

  document.getElementById('f_pair').addEventListener('change', renderTop);
  document.getElementById('f_tf').addEventListener('change', renderTop);

  renderHeat();
  renderTop();
</script>
</body>
</html>
"""
    return html

# -----------------------------------------------------------------------------
# Publication GitHub Pages
# -----------------------------------------------------------------------------

def publish_pages():
    try:
        from tools import publish_pages as pub
        print("[render] publish via import tools.publish_pages …")
        pub.main()
        return
    except Exception as e:
        print(f"[render] ⚠️Publication ignorée (erreur import): {e}")
        # trace si utile:
        # traceback.print_exc()

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main():
    data = read_inputs()
    html = render_html(data)

    index_path = DOCS_DIR / "index.html"
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    index_path.write_text(html, encoding="utf-8")
    print(f"[render] Écrit → {index_path}")

    # publication auto (copie JSON + push GH Pages)
    publish_pages()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[render] FATAL: {e}")
        traceback.print_exc()
        sys.exit(1)