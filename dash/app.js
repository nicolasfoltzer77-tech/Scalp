const $ = s => document.querySelector(s);
const log = (m) => {
  const el = $("#logs");
  const ts = new Date().toISOString().replace('T',' ').slice(0,19);
  el.textContent = `[${ts}] ${m}\n` + el.textContent;
};

function setTab(name){
  document.querySelectorAll('.tab').forEach(t=>{
    t.classList.toggle('active', t.dataset.tab === name);
  });
  ["flux","heatmap","historique"].forEach(v=>{
    $("#view-"+v).hidden = (v !== name);
  });
  localStorage.setItem('rtviz.tab', name);
}
document.querySelectorAll('.tab').forEach(t=> t.onclick = ()=> setTab(t.dataset.tab));
setTab(localStorage.getItem('rtviz.tab') || 'heatmap');

/* ----- API status (REST léger pour version) ----- */
async function getJSON(url){ const r=await fetch(url); if(!r.ok) throw new Error(r.statusText); return r.json(); }
async function refreshStatus(){
  try{
    const info = await getJSON('/viz/test');
    $('#apiVer').textContent = info.ver || '—';
    $('#apiTs').textContent = (info.ts || '').replace('T',' ').replace('Z','');
    $('#statusBox').innerHTML = `<span style="color:#42d392">OK</span> • ${info.ver}`;
  }catch(e){
    $('#statusBox').innerHTML = `<span style="color:#ff5d5d">DOWN</span> • ${e.message}`;
    log(`API test error: ${e.message}`);
  }
}

/* ----- Heatmap renderer ----- */
const hm = {
  canvas: null, ctx: null, nx: 0, ny: 0,
  draw(data){
    if(!data || !Array.isArray(data.cells)) return;
    const cells = data.cells;
    this.nx = 1 + Math.max(...cells.map(c=>c.x));
    this.ny = 1 + Math.max(...cells.map(c=>c.y));
    const dpr = window.devicePixelRatio || 1;
    const W = this.canvas.clientWidth, H = this.canvas.clientHeight;
    this.canvas.width = W*dpr; this.canvas.height = H*dpr;
    this.ctx.setTransform(dpr,0,0,dpr,0,0);
    this.ctx.clearRect(0,0,W,H);
    const cw=W/this.nx, ch=H/this.ny;
    for(const c of cells){
      const v = Math.max(0, Math.min(1, Number(c.v)||0));
      const col = valueToGreen(v);
      this.ctx.fillStyle = col;
      this.ctx.fillRect(c.x*cw, c.y*ch, Math.ceil(cw), Math.ceil(ch));
    }
    this.ctx.strokeStyle = '#20263a';
    for(let i=0;i<=this.nx;i++){ this.ctx.beginPath(); this.ctx.moveTo(i*cw,0); this.ctx.lineTo(i*cw,H); this.ctx.stroke(); }
    for(let j=0;j<=this.ny;j++){ this.ctx.beginPath(); this.ctx.moveTo(0,j*ch); this.ctx.lineTo(W,j*ch); this.ctx.stroke(); }
    $("#hmAsOf").textContent = (data.as_of || '').replace('T',' ').replace('Z','');
  }
};
function valueToGreen(v){
  const c0=[0x13,0x2a,0x1e], c1=[0x2e,0xcc,0x71];
  const mix=i=>Math.round(c0[i]+(c1[i]-c0[i])*v); return `rgb(${mix(0)},${mix(1)},${mix(2)})`;
}

/* ----- Flux table ----- */
function addSignalRow(sig){
  const tb = $("#tbl-flux tbody");
  if(tb.querySelector('.muted')) tb.innerHTML='';
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td class="mono">${(sig.ts||'').replace('T',' ').slice(0,19)}</td>
    <td class="mono">${sig.sym||'—'}</td>
    <td class="${sig.side==='BUY'?'buy':'sell'}">${sig.side||'?'}</td>
    <td class="mono">${Number(sig.score||0).toFixed(2)}</td>
    <td class="mono">${Number(sig.entry||0).toFixed(2)}</td>`;
  tb.prepend(tr);
  while(tb.children.length>20) tb.lastElementChild.remove();
}

/* ----- SSE connection ----- */
let es, retryMs = 1000;
function connectSSE(){
  if(es){ es.close(); es=null; }
  es = new EventSource('/viz/stream');
  es.addEventListener('open', () => {
    log('SSE connecté'); retryMs = 1000;
  });
  es.addEventListener('error', () => {
    log('SSE déconnecté, retry…'); es.close(); es=null;
    setTimeout(connectSSE, Math.min(retryMs*=2, 15000));
  });
  es.addEventListener('hello', ev => log('hello '+ev.data));
  es.addEventListener('tick',  () => {}); // keep-alive
  es.addEventListener('heatmap', ev => {
    try{ const msg = JSON.parse(ev.data); hm.draw(msg.data||msg); }catch(e){ log('parse heatmap fail'); }
  });
  es.addEventListener('signal', ev => {
    try{ const msg = JSON.parse(ev.data); addSignalRow(msg.data||msg); }catch(e){ log('parse signal fail'); }
  });
  // fallback: message generic
  es.onmessage = (ev)=>{ try{
      const m = JSON.parse(ev.data);
      if(m.type==='heatmap') hm.draw(m.data);
      else if(m.type==='signal') addSignalRow(m.data);
    }catch{}
  };
}

/* ----- Boot ----- */
window.addEventListener('load', () => {
  hm.canvas = $("#heatmap"); hm.ctx = hm.canvas.getContext('2d');
  refreshStatus();
  connectSSE();
  setInterval(refreshStatus, 5000); // version/health
  log('UI ready (SSE)');
});
