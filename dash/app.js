/* front-version: 3.13 */
// Helpers
const API = (p) => `/api/${p}`;
const $  = (s,r=document)=>r.querySelector(s);
const $$ = (s,r=document)=>[...r.querySelectorAll(s)];

let refreshSec = 3;           // période MAJ
let ct = refreshSec;          // compteur
let tf = 2;                   // 1/2/3 (placeholder)
let state = {mode:'paper', risk_level:2, balance:1000};

// --- UI init
const el = {
  ver: $('.js-ver'),
  ct: $('.js-ct'),
  modeTxt: $('.js-mode'),
  bal: $('.js-bal'),
  ccy: $('.js-ccy'),
  btnMode: $('#btnMode'),
  risks: $$('.js-risk'),
  tfs: $$('.js-tf'),
  tabBtns: $$('.js-tab'),
  views: $$('.js-view'),
  signalsBody: $('.js-signals-body'),
  positionsBody: $('.js-positions-body'),
  heat: $('.js-heat'),
  analyse: $('.js-analyse')
};

// boutons tabs
el.tabBtns.forEach(b=>{
  b.addEventListener('click', ()=>{
    el.tabBtns.forEach(x=>x.classList.remove('active'));
    b.classList.add('active');
    const v = b.dataset.tab;
    el.views.forEach(p => p.hidden = (p.dataset.view!==v));
  });
});

// bascule mode (affiche juste solde; POST /api/mode)
el.btnMode.addEventListener('click', async ()=>{
  const next = (state.mode==='paper') ? 'real' : 'paper';
  try{
    const r = await fetch(API('mode'), {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({mode:next})});
    if(r.ok){ state = await r.json(); renderState(); tickNow(); }
  }catch{}
});

// risques
el.risks.forEach(b=>{
  b.addEventListener('click', async ()=>{
    const lvl = +b.dataset.k;
    try{
      const r = await fetch(API('risk'), {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({risk_level:lvl})});
      if(r.ok){ state = await r.json(); renderState(); tickNow(); }
    }catch{}
  });
});

// tfs (placeholder visuel)
el.tfs.forEach(b=>{
  b.addEventListener('click', ()=>{ el.tfs.forEach(x=>x.classList.remove('active')); b.classList.add('active'); tf=+b.dataset.tf; });
});

function renderState(){
  el.modeTxt.textContent = state.mode.toUpperCase();
  el.bal.textContent = Math.round(state.balance);
  el.btnMode.textContent = Math.round(state.balance); // bouton = solde uniquement
  el.risks.forEach(b=> b.classList.toggle('active', +b.dataset.k===state.risk_level));
}
function fmtTS(ts){
  try{
    const d = typeof ts==='string'? new Date(ts) : new Date(ts*1000);
    return d.toISOString().substring(11,19);
  }catch{return '—'}
}

// --- DATA loaders
async function loadState(){
  const r = await fetch(API('state')); if(!r.ok) return;
  state = await r.json(); renderState();
}
async function loadSignals(){
  const r = await fetch(API('signals')); if(!r.ok) return;
  const rows = await r.json();
  el.signalsBody.innerHTML = rows.map(s=>`
    <tr><td>${fmtTS(s.ts)}</td><td>${s.sym}</td><td>${s.side}</td>
    <td>${s.score}</td><td>${s.qty}</td><td>${s.sl||''}</td><td>${(s.tp||[]).join(' · ')}</td></tr>
  `).join('');
}
async function loadPositions(){
  const r = await fetch(API('positions')); if(!r.ok) return;
  const rows = await r.json();
  el.positionsBody.innerHTML = rows.map(p=>`
    <tr><td>${fmtTS(p.ts)}</td><td>${p.id||''}</td><td>${p.sym}</td>
    <td>${p.side}</td><td>${p.entry??''}</td><td>${p.qty??''}</td></tr>
  `).join('');
}
async function loadHeat(){
  const r = await fetch(API('heatmap')); if(!r.ok) return;
  const items = await r.json();
  // items: [{sym, pct(0-1)}]
  el.heat.innerHTML = items.map(it=>{
    const score = Math.max(0, Math.min(100, Math.round((it.pct||0)*100)));
    return `<div class="tile">
      <div class="sym small">${(it.sym||'').replace('USDT','')}</div>
      <div class="score">${score}</div>
    </div>`;
  }).join('');
}
async function loadAnalyse(){
  const r = await fetch(API('analyse')); if(!r.ok) return;
  const a = await r.json();
  const note = a.best ? Math.max(0,Math.min(100, Math.round((a.best.buy_threshold||0)*100))) : 0;
  el.analyse.innerHTML = `
    <div class="row">
      <div class="card" style="flex:1">
        <div class="small meta">Meilleure crypto</div>
        <div style="font-size:22px;font-weight:800">${a.best?.sym || '—'}</div>
        <div class="meta">${a.best?.reason || ''}</div>
        <div class="hr"></div>
        <div class="small">Seuil d'achat (fictif)</div>
        <div style="font-size:18px">${a.best?.buy_threshold ?? '—'} (${note})</div>
      </div>
    </div>
  `;
}

// --- Ticker
function tickNow(){ ct = refreshSec; el.ct.textContent = ct; }
setInterval(async ()=>{
  ct--; if(ct<0){ ct=0 } el.ct.textContent = ct;
  if(ct===0){
    try{
      await Promise.all([loadState(), loadSignals(), loadPositions(), loadHeat(), loadAnalyse()]);
    }finally{ tickNow(); }
  }
}, 1000);

// boot
(async function init(){
  el.ver.textContent = '3.13';
  renderState();
  await Promise.all([loadState(), loadSignals(), loadPositions(), loadHeat(), loadAnalyse()]);
  tickNow();
})();
