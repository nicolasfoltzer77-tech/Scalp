#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCALP — Génère un dashboard HTML dynamique dans /docs
et publie sur GitHub Pages (copie JSON + health.json + push).

Robustesse :
- Ajoute les chemins candidats dans sys.path
- Essaye importlib (tools.publish_pages -> main())
- Sinon cherche publish_pages.py dans plusieurs emplacements et exécute
- Journalise tous les chemins testés
"""

from __future__ import annotations
import os, sys, subprocess, importlib, traceback
from pathlib import Path

# ----------------- Réglages -----------------
AUTO_REFRESH_SECS = int(os.environ.get("AUTO_REFRESH_SECS", "5"))

# ----------------- Chemins de base -----------------
THIS_FILE  = Path(__file__).resolve()
REPO_ROOT  = THIS_FILE.parents[1]              # <repo>
DOCS_DIR   = REPO_ROOT / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)

# Certains dumps ont la structure <repo>/scalp/...
POSSIBLE_ROOTS = [REPO_ROOT, REPO_ROOT / "scalp"]

# Assurer sys.path propre
for root in POSSIBLE_ROOTS:
    if root.exists() and str(root) not in sys.path:
        sys.path.insert(0, str(root))

# ----------------- HTML (UI dynamique) -----------------
HTML = f"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SCALP — Dashboard</title>
<style>
  :root {{ --ok:#0a910a; --dat:#b88600; --old:#d90000; --mis:#6b7280; --muted:#6b7280; --border:#e8e8e8; --bg:#fafafa; }}
  body {{ font-family: system-ui,-apple-system,Segoe UI,Roboto,sans-serif; margin: 20px; color:#111; }}
  h1 {{ font-size: 28px; margin: 0 0 10px; }} h2 {{ font-size: 20px; margin: 0 0 10px; }}
  .row {{ display:flex; gap:16px; flex-wrap:wrap; align-items:center; }}
  .card {{ border:1px solid var(--border); border-radius:10px; padding:14px 16px; margin:16px 0; background:#fff; }}
  .pill {{ display:inline-block; margin:4px 8px; padding:4px 10px; border-radius:14px; color:#fff; font-weight:600; }}
  .pill.ok  {{ background: var(--ok); }} .pill.dat {{ background: var(--dat); }} .pill.old {{ background: var(--old); }} .pill.mis {{ background: var(--mis); }}
  .muted {{ color: var(--muted); font-size:12px; }} .mono {{ font-family: ui-monospace,Menlo,Consolas,monospace; }}
  .grid-2 {{ display:grid; grid-template-columns:1fr; gap:16px; }} @media (min-width:980px){{ .grid-2 {{ grid-template-columns:1fr 1fr; }} }}
  table {{ border-collapse: collapse; width: 100%; }} th,td {{ border:1px solid #eee; padding:6px 8px; text-align:left; }}
  th {{ background: var(--bg); cursor: pointer; user-select:none; }}
  th.sort-asc::after {{ content:" \\25B2"; }} th.sort-desc::after {{ content:" \\25BC"; }}
  .status-OK{{color:var(--ok);font-weight:700}} .status-DAT{{color:var(--dat);font-weight:700}}
  .status-OLD{{color:var(--old);font-weight:700}} .status-MIS{{color:var(--mis);font-weight:700}}
  .controls .block{{margin-right:16px}} .controls input[type="number"]{{width:90px}} .controls label{{margin-right:8px}}
  .health-ok{{color:var(--ok);font-weight:700}} .health-warn{{color:var(--dat);font-weight:700}} .health-bad{{color:var(--old);font-weight:700}}
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

<div class="card"><h2>Heatmap (pair × TF)</h2><div id="heatmap">Chargement…</div></div>

<div class="card">
  <h2>TOP résultats</h2>
  <div class="controls row" style="margin-bottom:10px">
    <div class="block"><label>Pair :</label><input type="text" id="filterPair" placeholder="ex: BTC" /></div>
    <div class="block"><label>TF :</label>
      <label><input type="checkbox" class="tfChk" value="1m" checked>1m</label>
      <label><input type="checkbox" class="tfChk" value="3m">3m</label>
      <label><input type="checkbox" class="tfChk" value="5m" checked>5m</label>
      <label><input type="checkbox" class="tfChk" value="15m" checked>15m</label>
      <label><input type="checkbox" class="tfChk" value="30m">30m</label>
    </div>
    <div class="block"><label>min PF :</label><input type="number" id="minPF" step="0.01" value="1.20"></div>
    <div class="block"><label>max MDD % :</label><input type="number" id="maxMDD" step="1" value="30"></div>
    <div class="block"><label>min trades :</label><input type="number" id="minTR" step="1" value="25"></div>
    <div class="block"><button id="btnApply">Appliquer filtres</button><button id="btnReset">Reset</button></div>
  </div>
  <div id="topTableWrap">Chargement…</div>
</div>

<div class="card"><h2>Dernières actions</h2>
  <pre id="lastErrors" class="mono" style="white-space:pre-wrap;background:#fafafa;padding:10px;border-radius:8px;border:1px solid #eee;">Chargement…</pre>
</div>

<script>
const AUTO_REFRESH_SECS = {AUTO_REFRESH_SECS};
let countdown = AUTO_REFRESH_SECS;
function ts(){{const d=new Date();return d.toISOString().replace('T',' ').substring(0,19)+' UTC';}}
function setNow(){{document.getElementById('now').textContent='('+ts()+')';}}
function tick(){{countdown-=1;if(countdown<=0)location.reload();document.getElementById('countdown').textContent='reload dans '+countdown+'s';}}
document.getElementById('btnRefresh').addEventListener('click',()=>location.reload());

function badge(st){{return `<td class="status-${{st}}">${{st}}</td>`;}}
function counters(c){{for(const k of ["MIS","OLD","DAT","OK"]){{const el=document.getElementById(k);el.textContent=`${{k}}: ${{c[k]||0}}`;}}}}
function heatmap(matrix,tf){{if(!matrix||!matrix.length){{document.getElementById('heatmap').innerHTML="<div class='muted'>Aucune matrice.</div>";return;}}
  let h="<table><thead><tr><th>PAIR</th>"+tf.map(t=>`<th>${{t}}</th>`).join("")+"</tr></thead><tbody>";
  for(const row of matrix){{h+=`<tr><td><b>${{row.pair}}</b></td>`;for(const t of tf){{h+=badge(row[t]||"MIS");}}h+="</tr>";}}
  h+="</tbody></table>";document.getElementById('heatmap').innerHTML=h;
}}
let sortState={{col:"score",dir:"desc"}};
function score(r){{const pf=+r.pf||0,mdd=+r.mdd||0,sh=+r.sharpe||0,wr=+r.wr||0;return pf*2+sh*0.5+wr*0.5-mdd*1.5;}}
function filters(){{const q=document.getElementById('filterPair').value.trim().toUpperCase();
  const tfs=[...document.querySelectorAll('.tfChk:checked')].map(x=>x.value);const minPF=+document.getElementById('minPF').value||0;
  const maxMDD=(+document.getElementById('maxMDD').value||100)/100.0;const minTR=+document.getElementById('minTR').value||0;
  return {{q,tfs,minPF,maxMDD,minTR}};
}}
function apply(rows){{const f=filters();return rows.filter(r=>{{const okPair=!f.q||(r.pair||"").toUpperCase().includes(f.q);const okTF=f.tfs.length===0||f.tfs.includes(r.tf);
  return okPair && ((+r.pf||0)>=f.minPF) && ((+r.mdd||0)<=f.maxMDD) && ((+r.trades||0)>=f.minTR);}});}}
function sortRows(rows,col,dir){{const m=dir==="asc"?1:-1;return rows.slice().sort((a,b)=>(((a[col]??0)>(b[col]??0))?1:(a[col]??0)<(b[col]??0)?-1:0)*m);}}
function renderTop(rowsAll){{const rows=rowsAll.map(r=>Object.assign({{}},r,{{score:score(r)}}));const data=apply(rows);
  const cols=[{{key:"rank",label:"#"}},{{key:"pair",label:"PAIR"}},{{key:"tf",label:"TF"}},{{key:"pf",label:"PF"}},{{key:"mdd",label:"MDD"}},{{key:"trades",label:"TR"}},{{key:"wr",label:"WR"}},{{key:"sharpe",label:"Sharpe"}},{{key:"score",label:"Note"}}];
  const sorted=sortRows(data,sortState.col,sortState.dir);
  let h="<table><thead><tr>";for(const c of cols){{const cls=(sortState.col===c.key)?("sort-"+sortState.dir):"";h+=`<th data-col="${{c.key}}" class="${{cls}}">${{c.label}}</th>`;}}h+="</tr></thead><tbody>";
  sorted.slice(0,100).forEach((r,i)=>{{h+=`<tr><td>${{i+1}}</td><td>${{r.pair}}</td><td>${{r.tf}}</td><td>${{(+r.pf).toFixed(3)}}</td><td>${{((+r.mdd)*100).toFixed(1)}}%</td><td>${{r.trades||0}}</td><td>${{((+r.wr)*100).toFixed(1)}}%</td><td>${{(+r.sharpe).toFixed(2)}}</td><td>${{(+r.score).toFixed(2)}}</td></tr>`;}});h+="</tbody></table>";
  const w=document.getElementById('topTableWrap');w.innerHTML=h;w.querySelectorAll("th").forEach(th=>th.addEventListener("click",()=>{{const col=th.dataset.col;if(!col)return;
    (sortState.col===col)?(sortState.dir=(sortState.dir==="asc"?"desc":"asc")):(sortState.col=col,sortState.dir="desc");renderTop(rowsAll);}}));
}}
async function j(path){{const u=path+"?_t="+Date.now();const r=await fetch(u);if(!r.ok)throw new Error("HTTP "+r.status+" "+path);return await r.json();}}
async function refreshAll(){{setNow();let status={{}},summary={{}},last={{}},health={{}};try{{[status,summary,last,health]=await Promise.all([j("data/status.json").catch(_=>({{}})),j("data/summary.json").catch(_=>({{}})),j("data/last_errors.json").catch(_=>({{}})),j("health.json").catch(_=>({{}}))]);}}catch(e){{console.error(e);}}
  const hb=document.getElementById('healthBody');if(Object.keys(health).length){{const st=(health.status||"").toLowerCase();const cls=st.includes("ok")?"health-ok":(st.includes("local")||st.includes("no-change")?"health-warn":"health-bad");
    hb.innerHTML=`<div>generated_at: <b>${{health.generated_at||"?"}}</b></div><div>commit: <span class="mono">${{(health.commit||"").substring(0,10)}}</span></div><div>status: <span class="${{cls}}">${{health.status}}</span></div>`;}}
  else hb.textContent="health.json manquant (ok si premier run).";
  counters(status.counts||{{}});const tf=(status.matrix&&status.matrix[0])?Object.keys(status.matrix[0]).filter(k=>k!=="pair"):["1m","5m","15m"];heatmap(status.matrix||[],tf);
  renderTop(summary.rows||[]);document.getElementById('lastErrors').textContent=JSON.stringify(last,null,2);
}}
document.getElementById('btnApply').addEventListener('click',()=>refreshAll());
document.getElementById('btnReset').addEventListener('click',()=>{{document.getElementById('filterPair').value="";document.querySelectorAll('.tfChk').forEach(ch=>ch.checked=(["1m","5m","15m"].includes(ch.value)));document.getElementById('minPF').value="1.20";document.getElementById('maxMDD').value="30";document.getElementById('minTR').value="25";refreshAll();}});
setNow();refreshAll();setInterval(tick,1000);
</script>
"""

# ----------------- Publication robuste -----------------
def _try_import_and_run():
    """
    Essaie : import tools.publish_pages et appelle main().
    Retourne True si exécuté, False sinon.
    """
    try:
        mod = importlib.import_module("tools.publish_pages")
        if hasattr(mod, "main"):
            print("[render] publish via import tools.publish_pages …")
            mod.main()
            return True
    except Exception:
        traceback.print_exc()
    return False

def _try_run_script():
    """
    Cherche un fichier publish_pages.py dans plusieurs emplacements et l'exécute.
    Retourne True si exécuté, False sinon.
    """
    candidates = [
        REPO_ROOT / "tools" / "publish_pages.py",
        REPO_ROOT / "scalp" / "tools" / "publish_pages.py",
    ]
    print("[render] candidats publish_pages:", ", ".join(str(p) for p in candidates))
    for p in candidates:
        if p.exists():
            print(f"[render] publish via fichier: {p}")
            try:
                subprocess.run([sys.executable, str(p)], cwd=str(REPO_ROOT), check=True)
                return True
            except Exception:
                traceback.print_exc()
    return False

def _publish():
    # 1) import direct si possible
    if _try_import_and_run():
        return
    # 2) sinon exécution d’un fichier trouvé
    if _try_run_script():
        return
    # 3) dernier recours : -m (utile si package bien installé)
    try:
        print("[render] publish via -m tools.publish_pages …")
        subprocess.run([sys.executable, "-m", "tools.publish_pages"], cwd=str(REPO_ROOT), check=True)
    except Exception:
        traceback.print_exc()
        print("[render] ⚠️ Publication ignorée (module introuvable).")

# ----------------- Main -----------------
def main():
    # écrire HTML
    (DOCS_DIR / "index.html").write_text(HTML, encoding="utf-8")
    (DOCS_DIR / "dashboard.html").write_text(HTML, encoding="utf-8")
    print(f"[render] Écrit → {DOCS_DIR / 'index.html'}")

    # publier (robuste)
    _publish()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[render] FATAL: {e}")
        sys.exit(1)