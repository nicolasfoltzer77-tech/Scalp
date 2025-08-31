/* SCALP – Front Data/Render (vanilla JS) */

const DS = {
  signals: '/signals.json',
  positions: '/positions.json',
  balance: '/bitget_balance.json',
};

// ---------- helpers ----------
const qs  = (s, r=document)=>r.querySelector(s);
const qsa = (s, r=document)=>[...r.querySelectorAll(s)];
const fmt = new Intl.NumberFormat('en-US', {maximumFractionDigits: 2});

function showError(msg){
  let b = qs('#error-banner');
  if(!b){
    b = document.createElement('div');
    b.id = 'error-banner';
    b.style.cssText =
      'position:sticky;top:0;z-index:9999;background:#3b1111;color:#fecaca;padding:8px 12px;border-bottom:1px solid #dc2626;font:14px/1.3 system-ui';
    document.body.prepend(b);
  }
  b.textContent = msg || '';
  b.style.display = msg ? 'block' : 'none';
}

async function getJSON(url, {retries=2, timeout=8000} = {}) {
  for (let i=0;i<=retries;i++){
    try {
      const ctrl = new AbortController();
      const t = setTimeout(()=>ctrl.abort(), timeout);
      const res = await fetch(url, {
        signal: ctrl.signal,
        cache: 'no-store',
        headers: {'Cache-Control':'no-cache'},
      });
      clearTimeout(t);
      if(!res.ok) throw new Error(`HTTP ${res.status} on ${url}`);
      return await res.json();
    } catch(e){
      if(i===retries){ showError(e.message); throw e; }
      await new Promise(r=>setTimeout(r, 400*(i+1)));
    }
  }
}

// strip suffixes like USDT, PERP etc.
function baseSym(sym){
  if(!sym) return sym;
  return sym.replace(/USDT$|USD$|PERP$/,'');
}

// tiny score: BUY +2, SELL -2, HOLD 0; +1/-1 if a sub-strategy ≠ HOLD
function computeScore(rec){
  let s = 0;
  if(rec.signal === 'BUY')  s += 2;
  if(rec.signal === 'SELL') s -= 2;
  if(rec.details){
    const parts = String(rec.details).split(';');
    for(const p of parts){
      if(/=BUY$/.test(p))  s += 1;
      if(/=SELL$/.test(p)) s -= 1;
    }
  }
  return s;
}

function pillClass(signal){
  if(signal === 'BUY')  return 'pill pill--buy';
  if(signal === 'SELL') return 'pill pill--sell';
  return 'pill pill--hold';
}

// ---------- renderers ----------
function renderBalance(data){
  const el = qs('#bitget-balance');
  if(!el) return;
  if(!data || typeof data.equity_usdt !== 'number'){
    el.textContent = '—';
    return;
  }
  el.textContent = fmt.format(data.equity_usdt);
}

function renderHeatmap(signals, risk){
  const table = qs('#heatmap-body');
  if(!table) return;
  table.innerHTML = '';

  // map: base -> { '1m': rec, '5m': rec, '15m': rec, scoreXtf }
  const wantedTF = ['1m','5m','15m'];
  const grid = new Map();

  for(const rec of (signals||[])){
    if(!wantedTF.includes(rec.tf)) continue;
    const b = baseSym(rec.symbol);
    if(!grid.has(b)) grid.set(b, {});
    grid.get(b)[rec.tf] = rec;
  }

  // sort by base symbol
  const rows = [...grid.keys()].sort();
  for(const b of rows){
    const tr = document.createElement('tr');

    const c0 = document.createElement('td');
    c0.className = 'symb';
    c0.textContent = b;
    tr.appendChild(c0);

    for(const tf of wantedTF){
      const rec = grid.get(b)[tf];
      const cell = document.createElement('td');
      cell.className = 'cell';

      if(rec){
        const pill = document.createElement('div');
        pill.className = pillClass(rec.signal);
        pill.textContent = rec.signal;
        const score = document.createElement('div');
        score.className = 'score';
        score.textContent = computeScore(rec);
        cell.appendChild(pill);
        cell.appendChild(score);
      }else{
        const dash = document.createElement('div');
        dash.className = 'pill pill--muted';
        dash.textContent = '—';
        const score = document.createElement('div');
        score.className = 'score muted';
        score.textContent = '0';
        cell.appendChild(dash);
        cell.appendChild(score);
      }
      tr.appendChild(cell);
    }

    table.appendChild(tr);
  }

  // badge du risque
  qsa('[data-risk]').forEach(btn=>{
    btn.classList.toggle('active', String(btn.dataset.risk)===String(risk));
  });
}

function renderSignals(signals){
  const body = qs('#signals-body');
  if(!body) return;
  body.innerHTML = '';

  // garder seulement BUY/SELL
  const filtered = (signals||[]).filter(r => r.signal !== 'HOLD');

  // trier desc par ts
  filtered.sort((a,b)=>(b.ts||0)-(a.ts||0));

  for(const r of filtered.slice(0,50)){
    const tr = document.createElement('tr');

    const d0 = document.createElement('td');
    d0.textContent = r.ts ? new Date(r.ts*1000).toISOString().replace('T',' ').replace('.000Z',' UTC') : '—';

    const d1 = document.createElement('td');
    d1.textContent = baseSym(r.symbol);

    const d2 = document.createElement('td');
    d2.textContent = r.tf || '—';

    const d3 = document.createElement('td');
    const pill = document.createElement('span');
    pill.className = pillClass(r.signal);
    pill.textContent = r.signal;
    d3.appendChild(pill);

    const d4 = document.createElement('td');
    d4.textContent = r.details || '';

    tr.append(d0,d1,d2,d3,d4);
    body.appendChild(tr);
  }
}

function renderPositions(positions){
  const body = qs('#pos-body');
  if(!body) return;
  body.innerHTML = '';
  const list = Array.isArray(positions) ? positions : [];
  for(const p of list){
    const tr = document.createElement('tr');

    const t0 = document.createElement('td');
    t0.textContent = p.open_time || '—';
    const t1 = document.createElement('td');
    t1.textContent = baseSym(p.symbol || '');

    const t2 = document.createElement('td');
    t2.textContent = p.side || '—';

    const t3 = document.createElement('td');
    t3.textContent = p.qty ?? '—';

    const t4 = document.createElement('td');
    t4.textContent = p.entry ?? '—';

    const t5 = document.createElement('td');
    t5.textContent = p.exit ?? '—';

    const t6 = document.createElement('td');
    t6.textContent = (typeof p.pnl_usdt === 'number') ? fmt.format(p.pnl_usdt) : '—';

    const t7 = document.createElement('td');
    const btn = document.createElement('button');
    btn.className = 'btn btn--ghost btn--xs';
    btn.textContent = 'Close';
    btn.disabled = true; // wiring broker à venir
    t7.appendChild(btn);

    tr.append(t0,t1,t2,t3,t4,t5,t6,t7);
    body.appendChild(tr);
  }
}

// ---------- state & refresh ----------
const state = {
  risk: localStorage.getItem('risk') || '2'
};

function wireRiskButtons(){
  qsa('[data-risk]').forEach(btn=>{
    btn.addEventListener('click', ()=>{
      state.risk = String(btn.dataset.risk);
      localStorage.setItem('risk', state.risk);
      // on ne recalcule pas côté back pour le risque pour l’instant,
      // on tag visuel seulement
      qsa('[data-risk]').forEach(b=>b.classList.toggle('active', b===btn));
    });
  });
}

async function refreshOnce(){
  try{
    const [signals, positions, balance] = await Promise.all([
      getJSON(DS.signals),
      getJSON(DS.positions),
      getJSON(DS.balance),
    ]);

    // online dot
    qs('#online-dot')?.classList.add('online');
    showError('');

    renderBalance(balance);
    renderHeatmap(signals, state.risk);
    renderSignals(signals);
    renderPositions(positions);

  }catch(e){
    qs('#online-dot')?.classList.remove('online');
    // showError déjà appelé par getJSON
  }finally{
    // nothing
  }
}

function loop(){
  refreshOnce().finally(()=>{
    setTimeout(loop, 5000); // 5s
  });
}

// boot
document.addEventListener('DOMContentLoaded', ()=>{
  wireRiskButtons();
  loop();
});
