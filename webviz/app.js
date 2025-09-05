// rtviz-ui front — 1.0.1
(() => {
  const $ = (s,p=document)=>p.querySelector(s);
  const $$ = (s,p=document)=>p.querySelectorAll(s);
  const UI_VERSION = window.UI_VERSION || "0.0.0";

  // Tabs
  $$('.tab').forEach(b=>{
    b.onclick=()=>{
      $$('.tab').forEach(x=>x.classList.remove('active'));
      b.classList.add('active');
      const t=b.dataset.tab;
      $('#pane-flux').style.display = (t==='flux')?'block':'none';
      $('#pane-heatmap').style.display = (t==='heatmap')?'block':'none';
      $('#pane-hist').style.display = (t==='hist')?'block':'none';
    };
  });

  // Bouton de mise à jour
  async function checkVersion(silent=false){
    try{
      const r = await fetch('/version?ts='+Date.now(), {cache:'no-store'});
      if(!r.ok) throw new Error('version http '+r.status);
      const {ui} = await r.json();
      if(ui && ui !== UI_VERSION){
        const msg = $('#ver-msg');
        msg.textContent = `Nouvelle version disponible: ${ui} (vous: ${UI_VERSION})`;
        msg.style.display='inline-block';
        const btn = $('#btn-update');
        btn.classList.add('warn');
        btn.onclick = ()=>{
          // cache-bust total (URL + app.js)
          const u = new URL(location.href);
          u.searchParams.set('v', Date.now());
          location.replace(u.toString());
        };
      } else if (!silent) {
        const msg = $('#ver-msg');
        msg.textContent = `À jour (${UI_VERSION})`;
        msg.style.display='inline-block';
        setTimeout(()=>msg.style.display='none', 2500);
      }
    }catch(e){
      if(!silent){ console.warn(e); }
    }
  }
  $('#btn-update').onclick = ()=>checkVersion(false);
  checkVersion(true);

  // Flux (résumé simple)
  async function loadFlux(){
    $('#flux-err').style.display='none';
    try{
      const r = await fetch('/signals?ts='+Date.now(), {cache:'no-store'});
      if(!r.ok) throw new Error('http '+r.status);
      const arr = await r.json();
      const tb = $('#flux-table tbody');
      tb.innerHTML='';
      (arr.slice(0,50)).forEach(it=>{
        const tr = document.createElement('tr');
        const t = it.ts, sym = it.sym || it.symbol, tf = it.tf, side = it.side || it.signal, score = it.score ?? '', entry = it.entry ?? '';
        tr.innerHTML = `<td>${t}</td><td>${sym}</td><td>${tf}</td><td>${side}</td><td>${score}</td><td>${entry}</td>`;
        tb.appendChild(tr);
      });
      $('#flux-table').style.display='table';
    }catch(e){
      $('#flux-err').style.display='block';
    }
  }
  // Heatmap (affiche brut si JSON non conforme)
  async function loadHeat(){
    $('#heat-err').style.display='none';
    try{
      const r = await fetch('/heatmap?ts='+Date.now(), {cache:'no-store'});
      if(!r.ok) throw new Error('http '+r.status);
      const j = await r.json(); // attendu: {cells:[{sym,tf,side,v}]}
      const wrap = $('#heat-wrap'); wrap.innerHTML='';
      const cells = Array.isArray(j.cells)? j.cells : [];
      if(!cells.length){ wrap.textContent='(vide)'; return; }
      // regroupe par sym
      const map = {};
      cells.forEach(c=>{
        const sym=(c.sym||c.symbol||'').toUpperCase();
        const tf=(c.tf||'').toLowerCase();
        if(!map[sym]) map[sym]={};
        map[sym][tf]=c.side||c.signal||'';
      });
      const table = document.createElement('table');
      table.innerHTML = `<thead><tr><th>sym \\ tf</th><th>1m</th><th>5m</th><th>15m</th></tr></thead><tbody></tbody>`;
      Object.keys(map).sort().forEach(sym=>{
        const tr=document.createElement('tr');
        tr.innerHTML = `<td>${sym}</td><td>${map[sym]['1m']||''}</td><td>${map[sym]['5m']||''}</td><td>${map[sym]['15m']||''}</td>`;
        table.querySelector('tbody').appendChild(tr);
      });
      wrap.appendChild(table);
    }catch(e){
      $('#heat-err').style.display='block';
    }
  }

  // 1er chargement
  loadFlux();
  loadHeat();

  // auto-refresh light
  setInterval(()=>{ loadFlux(); }, 20_000);
  setInterval(()=>{ loadHeat(); }, 60_000);
})();
