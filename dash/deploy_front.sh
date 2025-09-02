#!/usr/bin/env bash
set -euo pipefail
cd /opt/scalp/dash

VER="$(cat VERSION | tr -d '\n\r ')"

# version.txt (pour lecture simple)
echo "$VER" > /opt/scalp/dash/version.txt

# index.html
cat > /opt/scalp/dash/index.html <<HTML
<!doctype html><html lang="fr"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Scalp</title>
<style>
:root{--bg:#0b0f17;--card:#111827;--text:#e6eef8;--muted:#9fb4d9;--line:#233049;--btn:#2d6cdf;--btn-active:#1db954}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,Segoe UI,Roboto,Inter,Arial,sans-serif}
.wrap{max-width:1200px;margin:10px auto;padding:10px}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:10px 0}
.h1{font-size:26px;font-weight:900}
.btn{background:var(--btn);color:#fff;border:none;border-radius:12px;padding:8px 12px;font-weight:700}
.btn.muted{background:#0f1624;color:var(--muted)}
.btn.active{background:var(--btn-active)}
.badge{font-size:12px;color:var(--muted)}
.hr{height:1px;background:var(--line);margin:8px 0}
.grid{display:grid;gap:8px}
@media(min-width:760px){.grid{grid-template-columns:repeat(4,1fr)}}
.box{background:#1a2233;padding:10px;border-radius:8px;text-align:center}
.box .sym{font-weight:800;font-size:14px}
.box .score{font-size:12px;color:var(--muted)}
.kv{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.kv .k{color:var(--muted);font-size:12px}
.kv .v{font-weight:800}
.log{font-family:ui-monospace,Consolas,monospace;font-size:12px;white-space:pre-wrap;background:#0f1624;border-radius:8px;padding:8px}
</style>
</head><body><div class="wrap">
<!-- FRONT v ${VER} -->
<div class="row">
  <button class="btn muted" id="risk0">0</button>
  <button class="btn muted" id="risk1">1</button>
  <button class="btn active" id="risk2">2</button>
  <button class="btn muted" id="risk3">3</button>

  <div class="badge" id="ver">v ${VER}</div>
  <div class="badge" id="maj">maj : —</div>
  <div class="badge" id="mode">REAL</div>
  <div class="badge"><span id="bal">0</span> USDT</div>
</div>

<div class="card">
  <div class="h1">Signaux récents</div>
  <div class="hr"></div>
  <div class="row" style="gap:16px;flex-wrap:nowrap;overflow-x:auto">
    <div class="kv"><div class="k">ts</div><div class="k">sym</div><div class="k">side</div><div class="k">score</div><div class="k">qty</div><div class="k">sl</div><div class="k">tp</div></div>
  </div>
  <div id="signals"></div>
</div>

<div class="card">
  <div class="h1">Positions</div>
  <div class="hr"></div>
  <div class="kv"><div class="k">ts</div><div class="k">id</div><div class="k">sym</div><div class="k">side</div><div class="k">entry</div><div class="k">qty</div></div>
  <div id="positions"></div>
</div>

<div class="card">
  <div class="h1">Watchlist — Heatmap</div>
  <div class="hr"></div>
  <div class="grid" id="heat"></div>
</div>

<div class="card">
  <div class="h1">Analyse</div>
  <div class="hr"></div>
  <div id="analyse"></div>
</div>

<div class="card">
  <div class="h1">Logs</div>
  <div class="hr"></div>
  <div class="log" id="logs"></div>
</div>

<script src="/app.js?v=${VER}"></script>
</div></body></html>
HTML

# app.js
cat > /opt/scalp/dash/app.js <<'JS'
/* front-version: {{VER}} */
const API = (p)=>`/api/${p}`;
const $  = (s,r=document)=>r.querySelector(s);
const $$ = (s,r=document)=>[...r.querySelectorAll(s)];
const logs = (m)=>{ const el=$("#logs"); el.textContent = (m+"\n"+el.textContent).slice(0,8000); };

let tick=0, mode="REAL", risk=2, last=0;

const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const pctColor = (p)=>{ // p in 0..100
  const v = clamp(p,0,100)/100; // 0..1
  const g = Math.floor(40+150*v);
  const r = Math.floor(140-120*v);
  return `rgb(${r},${g},70)`;
};

function setPills(){
  $$("#risk0,#risk1,#risk2,#risk3").forEach((b,i)=>{
    b.classList.toggle("active", i===risk);
    b.classList.toggle("muted",  i!==risk);
    b.onclick=()=>{risk=i;};
  });
}

function renderHeatmap(d){
  const items = Array.isArray(d)? d : (d?.items||[]);
  const wrap = $("#heat"); wrap.innerHTML="";
  items.slice(0,40).forEach(x=>{
    const p = Math.round((x.pct??0)); // 0..100 entier
    const div = document.createElement("div");
    div.className="box";
    div.innerHTML = `<div class="sym">${(x.sym||"").replace("USDT","")}</div>
                     <div class="score">${p}</div>`;
    div.style.background = pctColor(p);
    wrap.appendChild(div);
  });
}

function renderSignals(d){
  const el=$("#signals"); el.innerHTML="";
  (d||[]).slice(0,12).forEach(s=>{
    const row = document.createElement("div");
    row.className="kv";
    row.innerHTML = `
      <div class="v">${s.ts||"-"}</div>
      <div class="v">${(s.sym||"").replace("USDT","")}</div>
      <div class="v">${s.side||"-"}</div>
      <div class="v">${Math.round(s.score||0)}</div>
      <div class="v">${s.qty||"-"}</div>
      <div class="v">${s.sl||"-"}</div>
      <div class="v">${s.tp||"-"}</div>`;
    el.appendChild(row);
  });
}

function renderPositions(d){
  const el=$("#positions"); el.innerHTML="";
  (d||[]).slice(0,10).forEach(p=>{
    const row = document.createElement("div");
    row.className="kv";
    row.innerHTML = `
      <div class="v">${p.ts||"-"}</div>
      <div class="v">${p.id||"-"}</div>
      <div class="v">${(p.sym||"").replace("USDT","")}</div>
      <div class="v">${p.side||"-"}</div>
      <div class="v">${p.entry||"-"}</div>
      <div class="v">${p.qty||"-"}</div>`;
    el.appendChild(row);
  });
}

function renderAnalyse(a){
  const el=$("#analyse");
  if(!a || !a.best){ el.textContent="—"; return; }
  el.innerHTML = `
    <div class="kv">
      <div class="k">meilleure</div><div class="v">${(a.best.sym||"").replace("USDT","")}</div>
      <div class="k">score</div><div class="v">${Math.round(a.best.score||0)}</div>
      <div class="k">achat &gt;</div><div class="v">${a.best.buy_above??"-"}</div>
    </div>
    <div class="badge">${a.reason||""}</div>`;
}

async function poll(){
  try{
    $("#maj").textContent = `maj : ${tick}s`;
    const [st, hm, sg, po, an] = await Promise.all([
      fetch(API("state")).then(r=>r.json()).catch(e=>{throw ["state",e]}),
      fetch(API("heatmap")).then(r=>r.json()).catch(e=>{throw ["heatmap",e]}),
      fetch(API("signals")).then(r=>r.json()).catch(e=>{throw ["signals",e]}),
      fetch(API("positions")).then(r=>r.json()).catch(e=>{throw ["positions",e]}),
      fetch(API("analyse")).then(r=>r.json()).catch(e=>null),
    ]);
    renderHeatmap(hm);
    renderSignals(sg);
    renderPositions(po);
    renderAnalyse(an);
    $("#bal").textContent = st?.balance ?? 0;
    mode = (st?.mode || "REAL").toUpperCase();
    $("#mode").textContent = mode;
    if(++tick>999) tick=0;
  }catch(err){
    const msg = Array.isArray(err)? `ERR ${err[0]} ${err[1]}` : (err?.message||String(err));
    logs(msg);
  }finally{
    setTimeout(poll, 1000);
  }
}

setPills();
poll();
JS

# injecter la version réelle dans l'entête de app.js
ver="$(cat /opt/scalp/dash/VERSION)"
sed -i "s/{{VER}}/$ver/" /opt/scalp/dash/app.js

# Droits
chown -R root:root /opt/scalp/dash
chmod 644 /opt/scalp/dash/index.html /opt/scalp/dash/app.js /opt/scalp/dash/version.txt
