// app.js
const API = (p) => `/api/${p}`;
const $ = (s, r=document) => r.querySelector(s);
const $$ = (s, r=document) => [...r.querySelectorAll(s)];

let state = { mode: 'paper', risk_level: 2, balance: 1000 };
let lastMaj = 0;

// Utils
const fmtTime = (ts) => {
  try {
    const d = typeof ts === 'string' ? new Date(ts) : new Date(ts*1000);
    return d.toISOString().substring(11,19); // HH:MM:SS
  } catch { return '—'; }
};
const baseSym = (sym) => {
  if (!sym) return '';
  sym = sym.toUpperCase();
  if (sym.endsWith('USDT')) sym = sym.replace('USDT','');
  return sym;
};
const pctColor = (p) => {
  // green -> red gradient
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
  const v = clamp(p, -3, 3); // [-3%, +3%] pour l’échelle
  if (v >= 0) {
    const g = Math.floor(70 + 120*(v/3));
    return `rgb(${40}, ${g}, ${70})`;
  } else {
    const r = Math.floor(80 + 120*(-v/3));
    return `rgb(${r}, 60, 70)`;
  }
};

async function getJSON(url){
  const r = await fetch(url, { cache:'no-store' });
  if(!r.ok) throw new Error(url+' -> '+r.status);
  return await r.json();
}

// State + header
async function refreshState(){
  try{
    state = await getJSON(API('state?v=3.4'));
    $('#balance').textContent = `bal ${state.balance ?? 1000} USDT`;
    // pills actives
    $$('#modeSeg .pill').forEach(b => b.classList.toggle('active', b.dataset.mode===state.mode));
    $$('#riskSeg .pill').forEach((b,i)=> b.classList.toggle('active', (i+1)===(state.risk_level||2)));
  }catch(e){ /* silently */ }
}

// Signals
async function refreshSignals(){
  try{
    const rows = await getJSON(API('signals?v=3.4'));
    const tb = $('#tblSignals tbody');
    tb.innerHTML = '';
    rows.slice(-30).reverse().forEach(s => {
      const side = (s.side||'').toUpperCase();
      const col = side==='SELL' ? 'sell':'buy';
      const price = s.entry?.price_ref ?? s.last_price ?? '—';
      const qty = s.qty ?? s.size_usdt ?? '—';
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td class="small">${fmtTime(s.ts)}</td>
        <td><span class="badge ${col}">${baseSym(s.symbol)}</span></td>
        <td class="small">${side||'—'}</td>
        <td>${(s.score??'—')=== '—' ? '—' : (s.score).toFixed(2)}</td>
        <td>${qty}</td>
        <td>${s.risk?.sl ?? '—'}</td>
        <td>${Array.isArray(s.risk?.tp) ? s.risk.tp[0] : (s.risk?.tp ?? '—')}</td>`;
      tb.appendChild(tr);
    });
  }catch(e){
    // vide => laisse la table
  }
}

// Positions + PnL papier (approx)
async function refreshPositions(){
  try{
    const rows = await getJSON(API('positions?v=3.4'));
    const tb = $('#tblPos tbody');
    tb.innerHTML = '';

    // Prépare quotes pour PnL
    const syms = [...new Set(rows.map(r => r.symbol).filter(Boolean))];
    let quotes = {};
    if (syms.length){
      const q = await getJSON(API('quotes?symbols='+encodeURIComponent(syms.join(','))+'&v=3.4'));
      quotes = q || {};
    }

    rows.slice(-40).reverse().forEach(p => {
      const side = (p.side||'').toUpperCase(); // LONG/SHORT
      const entry = Number(p.entry_price ?? p.entry?.price_ref ?? 0);
      const qty = Number(p.qty ?? p.size_usdt ?? 0);
      const q = quotes[p.symbol]?.last ?? null;
      let pnlTxt = '—', pnlCls='';
      if (entry>0 && qty>0 && q){
        const dir = side==='SHORT' ? -1 : 1;
        const ret = (q/entry - 1) * dir;        // rendement
        const pnl = ret * qty;                  // ~ USDT si qty est en USDT
        pnlTxt = (pnl>=0?'+':'') + pnl.toFixed(2);
        pnlCls = pnl>=0 ? 'pnl-pos':'pnl-neg';
      }

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td class="small">${fmtTime(p.ts)}</td>
        <td>${p.position_id ?? '—'}</td>
        <td><span class="badge">${baseSym(p.symbol)}</span></td>
        <td class="small">${side||'—'}</td>
        <td>${entry||'—'}</td>
        <td>${qty||'—'}</td>
        <td class="${pnlCls}">${pnlTxt}</td>`;
      tb.appendChild(tr);
    });
  }catch(e){
    // ignore
  }
}

// Heatmap
async function refreshHeatmap(tf='1m'){
  try{
    const data = await getJSON(API('heatmap?tf='+tf+'&v=3.4'));
    const root = $('#heatmap');
    root.innerHTML = '';
    data.forEach(it=>{
      const cell = document.createElement('div');
      const pct = Number(it.pct||0);
      cell.className = 'cell';
      cell.style.background = pctColor(pct);
      cell.innerHTML = `
        <div class="badge">${it.sym}</div>
        <div class="pct">${pct.toFixed(2)}%</div>`;
      root.appendChild(cell);
    });
  }catch(e){
    $('#heatmap').innerHTML = `<div class="small">Pas de données heatmap.</div>`;
  }
}

// Tabs
function showTab(id){
  $$('#main .view'); // placeholder if needed
  ['viewFlux','viewWatch','viewHist','viewML'].forEach(v=>{
    const el = $('#'+v); el.classList.toggle('hidden', v!==id);
  });
  // style boutons
  const map = {viewFlux:'#tabFlux', viewWatch:'#tabWatch', viewHist:'#tabHist', viewML:'#tabML'};
  ['#tabFlux','#tabWatch','#tabHist','#tabML'].forEach(sel=>$(sel).classList.remove('active'));
  $(map[id]).classList.add('active');
}

function wireUI(){
  // tabs
  $('#tabFlux').addEventListener('click', ()=> showTab('viewFlux'));
  $('#tabWatch').addEventListener('click', ()=> showTab('viewWatch'));
  $('#tabHist').addEventListener('click', ()=> showTab('viewHist'));
  $('#tabML').addEventListener('click',   ()=> showTab('viewML'));
  showTab('viewFlux');

  // TF boutons (placeholder, l’API utilise vol_ret mais on passe le tf)
  $$('#viewWatch [data-tf]').forEach(b=>{
    b.addEventListener('click', ()=>{
      $$('#viewWatch [data-tf]').forEach(x=>x.classList.remove('active'));
      b.classList.add('active');
      refreshHeatmap(b.dataset.tf);
    });
  });
  // activer 1m par défaut
  $('#viewWatch [data-tf="1m"]').classList.add('active');
}

async function tick(){
  await refreshState();
  await Promise.all([refreshSignals(), refreshPositions()]);
  lastMaj = Date.now();
  $('#maj').textContent = 'maj : ' + new Date(lastMaj).toISOString().substring(11,19);
}

async function boot(){
  wireUI();
  await tick();
  await refreshHeatmap('1m');
  setInterval(tick, 2000);
}

document.addEventListener('DOMContentLoaded', boot);
