/* front-version: __VER__ */
// Helpers
const API = (p) => `/api/${p}`;
const $  = (s, r=document) => r.querySelector(s);
const $$ = (s, r=document) => [...r.querySelectorAll(s)];

let lastTs = 0;

const fmtTime = (ts) => {
  try {
    const d = typeof ts === 'string' ? new Date(ts) : new Date(ts*1000);
    return d.toISOString().substring(11,19);
  } catch { return '—'; }
};

const baseSym = (s) => (s||'').toUpperCase().replace('USDT','');

const pctColor = (p) => {
  const clamp = (x,a,b)=>Math.max(a,Math.min(b,x));
  const v = clamp(p, -3, 3); // [-3%, +3%]
  if (v>=0){ const g = Math.floor(70+120*(v/3)); return `rgb(40, ${g}, 70)`; }
  else     { const r = Math.floor(80+120*(-v/3)); return `rgb(${r}, 60, 70)`; }
};

// Renderers
function renderState(st){
  $('.js-mode-pill').textContent = st.mode.toUpperCase();
  $('.js-balance').textContent = (st.balance ?? '—') + ' USDT';
  $$('.js-risk').forEach(b=>{
    b.classList.toggle('active', +b.dataset.risk === +st.risk_level);
    b.classList.toggle('muted',  +b.dataset.risk !== +st.risk_level);
  });
}

function renderSignals(rows){
  const body = $('.js-signals-body'); if (!body) return;
  body.innerHTML = rows.map(s => `
    <tr>
      <td>${fmtTime(s.ts)}</td>
      <td>${baseSym(s.symbol)}</td>
      <td>${s.side||''}</td>
      <td>${(s.score??'').toFixed ? s.score.toFixed(2): (s.score||'')}</td>
      <td>${s.qty||''}</td>
      <td>${s.risk?.sl ?? ''}</td>
      <td>${(s.risk?.tp||[]).join(' / ')}</td>
    </tr>`).join('');
}

function renderPositions(rows){
  const body = $('.js-positions-body'); if (!body) return;
  body.innerHTML = rows.map(p => `
    <tr>
      <td>${fmtTime(p.ts)}</td>
      <td>${p.position_id||p.id||''}</td>
      <td>${baseSym(p.symbol)}</td>
      <td>${p.side||''}</td>
      <td>${p.entry_price||p.entry||''}</td>
      <td>${p.qty||''}</td>
    </tr>`).join('');
}

function renderHeatmap(rows){
  const box = $('.js-heatmap'); if (!box) return;
  box.innerHTML = rows.slice(0,60).map(r => `
    <div class="cell" style="background:${pctColor(+r.pct||0)}">
      <div><b>${baseSym(r.sym)}</b></div>
      <div class="badge">${(+r.pct||0).toFixed(2)}%</div>
    </div>`).join('');
}

// Poll
async function refresh(){
  try{
    const [st, sig, pos, hm] = await Promise.all([
      fetch(API('state')).then(r=>r.json()),
      fetch(API('signals')).then(r=>r.json()).catch(()=>[]),
      fetch(API('positions')).then(r=>r.json()).catch(()=>[]),
      fetch(API('heatmap')).then(r=>r.json()).catch(()=>[])
    ]);
    if (st && st.ok){ renderState(st); }
    if (Array.isArray(sig)) renderSignals(sig);
    if (Array.isArray(pos)) renderPositions(pos);
    if (Array.isArray(hm))  renderHeatmap(hm);
    lastTs = Date.now();
  }catch(e){ /* silencieux */ }
}

setInterval(()=>{
  const secs = Math.max(0, Math.floor((Date.now()-lastTs)/1000));
  $('.js-refresh').textContent = secs;
}, 1000);

setInterval(refresh, 2000);
refresh();
