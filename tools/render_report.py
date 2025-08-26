#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCALP — Génère un dashboard HTML dynamique (vanilla JS) dans /docs :
- Charge status.json, summary.json, last_errors.json, health.json côté navigateur
- Affiche Health, compteurs MIS/OLD/DAT/OK, Heatmap pair×TF
- TOP filtrable (search pair, filtres TF, min PF, max MDD, min trades), tri par colonnes
- Auto-refresh avec compte à rebours + bouton Refresh
- À la fin, déclenche tools.publish_pages (copie JSON + push sur GitHub Pages)

Pré-requis côté pipeline :
- jobs/maintainer.py écrit reports/{status.json,last_errors.json}
- jobs/backtest.py écrit reports/summary.json
- tools/publish_pages.py copie ces JSON dans docs/data/ et pousse
"""

from __future__ import annotations
import os, sys, subprocess
from pathlib import Path

AUTO_REFRESH_SECS = int(os.environ.get("AUTO_REFRESH_SECS", "5"))

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR  = REPO_ROOT / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)

HTML = f"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SCALP — Dashboard</title>
<style>
  :root {{
    --ok:#0a910a; --dat:#b88600; --old:#d90000; --mis:#6b7280;
    --muted:#6b7280; --border:#e8e8e8; --bg:#fafafa;
  }}
  body {{ font-family: system-ui,-apple-system,Segoe UI,Roboto,sans-serif; margin: 20px; color:#111; }}
  h1 {{ font-size: 28px; margin: 0 0 10px; }}
  h2 {{ font-size: 20px; margin: 0 0 10px; }}
  .row {{ display:flex; gap:16px; flex-wrap:wrap; align-items:center; }}
  .card {{ border:1px solid var(--border); border-radius:10px; padding:14px 16px; margin:16px 0; background:#fff; }}
  .pill {{ display:inline-block; margin:4px 8px; padding:4px 10px; border-radius:14px; color:#fff; font-weight:600; }}
  .pill.ok  {{ background: var(--ok);  }}
  .pill.dat {{ background: var(--dat); }}
  .pill.old {{ background: var(--old); }}
  .pill.mis {{ background: var(--mis); }}

  .muted {{ color: var(--muted); font-size:12px; }}
  .mono {{ font-family: ui-monospace,Menlo,Consolas,monospace; }}

  .grid-2 {{ display:grid; grid-template-columns:1fr; gap:16px; }}
  @media (min-width: 980px) {{ .grid-2 {{ grid-template-columns:1fr 1fr; }} }}

  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border:1px solid #eee; padding:6px 8px; text-align:left; }}
  th {{ background: var(--bg); cursor: pointer; user-select: none; }}
  th.sort-asc::after  {{ content:" \\25B2"; }}
  th.sort-desc::after {{ content:" \\25BC"; }}

  .status-OK  {{ color: var(--ok);  font-weight:700; }}
  .status-DAT {{ color: var(--dat); font-weight:700; }}
  .status-OLD {{ color: var(--old); font-weight:700; }}
  .status-MIS {{ color: var(--mis); font-weight:700; }}

  .controls .block {{ margin-right: 16px; }}
  .controls input[type="number"] {{ width: 90px; }}
  .controls label {{ margin-right: 8px; }}

  .health-ok    {{ color: var(--ok);  font-weight:700; }}
  .health-warn  {{ color: var(--dat); font-weight:700; }}
  .health-bad   {{ color: var(--old); font-weight:700; }}
</style>

<h1>SCALP — Dashboard <span id="now" class="muted"></span></h1>
<div class="row">
  <div class="muted">Auto-refresh: <b>{AUTO_REFRESH_SECS}s</b> · <span id="countdown" class="muted"></span></div>
  <button id="btnRefresh">Refresh</button>
</div>

<div class="grid-2">
  <div class="card" id="healthCard">
    <h2>Health</h2>
    <div id="healthBody" class="mono muted">Chargement…</div>
  </div>

  <div class="card">
    <h2>Compteurs</h2>
    <div id="counters">
      <span class="pill mis" id="MIS">MIS: 0</span>
      <span class="pill old" id="OLD">OLD: 0</span>
      <span class="pill dat" id="DAT">DAT: 0</span>
      <span class="pill ok"  id="OK">OK: 0</span>
    </div>
    <div class="muted" style="margin-top:6px">MIS: no data · OLD: stale · DAT: fresh CSV, no active strategy · OK: fresh CSV + active strategy</div>
  </div>
</div>

<div class="card">
  <h2>Heatmap (pair × TF)</h2>
  <div id="heatmap">Chargement…</div>
</div>

<div class="card">
  <h2>TOP résultats</h2>

  <div class="controls row" style="margin-bottom:10px">
    <div class="block">
      <label>Pair :</label>
      <input type="text" id="filterPair" placeholder="ex: BTC" />
    </div>
    <div class="block">
      <label>TF :</label>
      <label><input type="checkbox" class="tfChk" value="1m" checked>1m</label>
      <label><input type="checkbox" class="tfChk" value="3m">3m</label>
      <label><input type="checkbox" class="tfChk" value="5m" checked>5m</label>
      <label><input type="checkbox" class="tfChk" value="15m" checked>15m</label>
      <label><input type="checkbox" class="tfChk" value="30m">30m</label>
    </div>
    <div class="block">
      <label>min PF :</label>
      <input type="number" id="minPF" step="0.01" value="1.20">
    </div>
    <div class="block">
      <label>max MDD % :</label>
      <input type="number" id="maxMDD" step="1" value="30">
    </div>
    <div class="block">
      <label>min trades :</label>
      <input type="number" id="minTR" step="1" value="25">
    </div>
    <div class="block">
      <button id="btnApply">Appliquer filtres</button>
      <button id="btnReset">Reset</button>
    </div>
  </div>

  <div id="topTableWrap">Chargement…</div>
</div>

<div class="card">
  <h2>Dernières actions</h2>
  <pre id="lastErrors" class="mono" style="white-space:pre-wrap;background:#fafafa;padding:10px;border-radius:8px;border:1px solid #eee;">Chargement…</pre>
</div>

<script>
const AUTO_REFRESH_SECS = {AUTO_REFRESH_SECS};
let countdown = AUTO_REFRESH_SECS;

function ts() {{
  const d = new Date();
  return d.toISOString().replace('T',' ').substring(0,19) + " UTC";
}}

function setNow() {{
  document.getElementById('now').textContent = "(" + ts() + ")";
}}

function tickCountdown() {{
  countdown -= 1;
  if (countdown <= 0) {{
    window.location.reload();
    return;
  }}
  document.getElementById('countdown').textContent = "reload dans " + countdown + "s";
}}

function badgeStatusCell(st) {{
  const cls = "status-" + st;
  return `<td class="${{cls}}">${{st}}</td>`;
}}

function renderCounters(counts) {{
  for (const k of ["MIS","OLD","DAT","OK"]) {{
    const el = document.getElementById(k);
    el.textContent = `${{k}}: ${{counts[k]||0}}`;
  }}
}}

function renderHeatmap(matrix, tf_list) {{
  if (!matrix || matrix.length === 0) {{
    document.getElementById('heatmap').innerHTML = "<div class='muted'>Aucune matrice (status.json manquant).</div>";
    return;
  }}
  let html = "<table><thead><tr><th>PAIR</th>";
  for (const tf of tf_list) html += `<th>${{tf}}</th>`;
  html += "</tr></thead><tbody>";
  for (const row of matrix) {{
    html += `<tr><td><b>${{row.pair}}</b></td>`;
    for (const tf of tf_list) {{
      const st = row[tf] || "MIS";
      html += badgeStatusCell(st);
    }}
    html += "</tr>";
  }}
  html += "</tbody></table>";
  document.getElementById('heatmap').innerHTML = html;
}}

let sortState = {{ col: "score", dir: "desc" }};

function sortRows(rows, col, dir) {{
  const m = dir === "asc" ? 1 : -1;
  return rows.slice().sort((a,b) => {{
    const va = a[col] ?? 0; const vb = b[col] ?? 0;
    return (va > vb ? 1 : va < vb ? -1 : 0) * m;
  }});
}}

function scoreRow(r) {{
  const pf = +r.pf||0, mdd = +r.mdd||0, sh=+r.sharpe||0, wr=+r.wr||0;
  return pf*2.0 + sh*0.5 + wr*0.5 - mdd*1.5;
}}

function getFilters() {{
  const q = document.getElementById('filterPair').value.trim().toUpperCase();
  const tfs = Array.from(document.querySelectorAll('.tfChk:checked')).map(x=>x.value);
  const minPF = parseFloat(document.getElementById('minPF').value || "0");
  const maxMDD = parseFloat(document.getElementById('maxMDD').value || "100");
  const minTR = parseInt(document.getElementById('minTR').value || "0");
  return {{ q, tfs, minPF, maxMDD, minTR }};
}}

function applyFilters(rows) {{
  const f = getFilters();
  return rows.filter(r => {{
    const okPair = !f.q || (r.pair||"").toUpperCase().includes(f.q);
    const okTF   = f.tfs.length===0 || f.tfs.includes(r.tf);
    const okPF   = (+r.pf||0) >= f.minPF;
    const okMDD  = (+r.mdd||0) <= (f.maxMDD/100.0);
    const okTR   = (+r.trades||0) >= f.minTR;
    return okPair && okTF && okPF && okMDD && okTR;
  }});
}}

function renderTopTable(allRows) {{
  // enrichir d'un score
  const rows = allRows.map(r => Object.assign({{}}, r, {{ score: scoreRow(r) }}));
  const filtered = applyFilters(rows);

  const cols = [
    {{key:"rank", label:"#"}},
    {{key:"pair", label:"PAIR"}},
    {{key:"tf", label:"TF"}},
    {{key:"pf", label:"PF"}},
    {{key:"mdd", label:"MDD"}},
    {{key:"trades", label:"TR"}},
    {{key:"wr", label:"WR"}},
    {{key:"sharpe", label:"Sharpe"}},
    {{key:"score", label:"Note"}}
  ];

  const sorted = sortRows(filtered, sortState.col, sortState.dir);

  let html = "<table><thead><tr>";
  for (const c of cols) {{
    const cls = (sortState.col===c.key) ? ("sort-" + sortState.dir) : "";
    html += `<th data-col="${{c.key}}" class="${{cls}}">${{c.label}}</th>`;
  }}
  html += "</tr></thead><tbody>";

  sorted.slice(0, 100).forEach((r,i) => {{
    html += "<tr>";
    html += `<td>${{i+1}}</td>`;
    html += `<td>${{r.pair}}</td>`;
    html += `<td>${{r.tf}}</td>`;
    html += `<td>${{(+r.pf).toFixed(3)}}`;
    html += `</td><td>${{((+r.mdd)*100).toFixed(1)}}%`;
    html += `</td><td>${{r.trades||0}}`;
    html += `</td><td>${{((+r.wr)*100).toFixed(1)}}%`;
    html += `</td><td>${{(+r.sharpe).toFixed(2)}}`;
    html += `</td><td>${{(+r.score).toFixed(2)}}`;
    html += "</td></tr>";
  }});
  html += "</tbody></table>";

  const wrap = document.getElementById('topTableWrap');
  wrap.innerHTML = html;

  // activer tri
  wrap.querySelectorAll("th").forEach(th => {{
    th.addEventListener("click", () => {{
      const col = th.dataset.col;
      if (!col) return;
      if (sortState.col === col) {{
        sortState.dir = (sortState.dir === "asc") ? "desc" : "asc";
      }} else {{
        sortState.col = col; sortState.dir = "desc";
      }}
      renderTopTable(allRows);
    }});
  }});
}}

async function loadJSON(path) {{
  // cache-buster pour forcer le rafraîchissement
  const url = path + "?_t=" + Date.now();
  const r = await fetch(url);
  if (!r.ok) throw new Error("HTTP "+r.status+" on "+path);
  return await r.json();
}}

async function refreshAll() {{
  setNow();
  countdown = AUTO_REFRESH_SECS;

  try {{
    // charge JSON depuis docs/data/
    const [status, summary, last, health] = await Promise.all([
      loadJSON("data/status.json").catch(_ => ({{}})),
      loadJSON("data/summary.json").catch(_ => ({{}})),
      loadJSON("data/last_errors.json").catch(_ => ({{}})),
      loadJSON("health.json").catch(_ => ({{}})),
    ]);

    // HEALTH
    const hb = document.getElementById('healthBody');
    if (Object.keys(health).length) {{
      const st = (health.status||"").toLowerCase();
      const cls = st.includes("ok") ? "health-ok" : (st.includes("local")||st.includes("no-change")?"health-warn":"health-bad");
      hb.innerHTML = `
        <div>generated_at: <b>${{health.generated_at||"?"}}</b></div>
        <div>commit: <span class="mono">${{(health.commit||"").substring(0,10)}}</span></div>
        <div>status: <span class="${{cls}}">${{health.status}}</span></div>
      `;
    }} else {{
      hb.textContent = "health.json manquant (ok si premier run).";
    }}

    // Compteurs + Heatmap
    const counts = (status.counts||{{}});
    renderCounters(counts);
    const tf_list = (status.matrix&&status.matrix[0]) ? Object.keys(status.matrix[0]).filter(k=>k!=="pair") : ["1m","5m","15m"];
    renderHeatmap(status.matrix||[], tf_list);

    // TOP table
    renderTopTable(summary.rows||[]);

    // Dernières actions
    const le = document.getElementById("lastErrors");
    le.textContent = JSON.stringify(last, null, 2);

  }} catch (e) {{
    console.error(e);
  }}
}}

document.getElementById('btnRefresh').addEventListener('click', () => {{
  window.location.reload();
}});
document.getElementById('btnApply').addEventListener('click', () => renderTopTable(window._lastRows||[]));
document.getElementById('btnReset').addEventListener('click', () => {{
  document.getElementById('filterPair').value = "";
  document.querySelectorAll('.tfChk').forEach(ch => ch.checked = (["1m","5m","15m"].includes(ch.value)));
  document.getElementById('minPF').value = "1.20";
  document.getElementById('maxMDD').value = "30";
  document.getElementById('minTR').value = "25";
  refreshAll();
}});

// Tick
setNow(); refreshAll();
setInterval(tickCountdown, 1000);
</script>
"""

def main():
    # Écrit la page (UI dynamique, pas de data embarquée)
    out1 = DOCS_DIR / "index.html"
    out2 = DOCS_DIR / "dashboard.html"
    out1.write_text(HTML, encoding="utf-8")
    out2.write_text(HTML, encoding="utf-8")
    print(f"[render] Écrit → {out1}")

    # Déclenche la publication (copie des JSON + health.json + push)
    try:
        subprocess.run([sys.executable, "-m", "tools.publish_pages"],
                       cwd=str(REPO_ROOT), check=True)
    except Exception as e:
        print(f"[render] Publication ignorée: {e}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[render] FATAL: {e}")
        sys.exit(1)