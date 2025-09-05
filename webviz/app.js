// rtviz-ui front
(() => {
  const $ = (s,p=document)=>p.querySelector(s);
  const $$ = (s,p=document)=>p.querySelectorAll(s);

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

  // Version / bouton update
  async function showVersionAndMaybeUpdate(){
    try{
      const r = await fetch('/version?ts='+Date.now(), {cache:'no-store'});
      const {ui} = await r.json();
      $('#ui-ver').textContent = ui || '(?)';
      // si le HTML/JS est ancien et le backend plus récent, on force un bouton rouge
      const htmlHas = new URL(location.href).searchParams.get('v') || '';
      const btn = $('#btn-update');
      btn.onclick = ()=>{
        const u = new URL(location.href);
        u.searchParams.set('v', Date.now()); // cache-bust total
        location.replace(u.toString());
      };
      // Si l’ancienne page ne montrait pas la même version, on colore le bouton
      if(!htmlHas){ btn.classList.add('warn'); }
    }catch(e){
      $('#ui-ver').textContent = '(?)';
    }
  }

  // Flux
  async function loadFlux(){
    $('#flux-err').style.display='none';
    try{
      const r = await fetch('/signals?ts='+Date.now(), {cache:'no-store'});
      if(!r.ok) throw new Error();
      const arr = await r.json();
      const tb = $('#flux-table tbody'); tb.innerHTML='';
      (arr.slice(0,50)).forEach(it=>{
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${it.ts}</td><td>${it.sym||it.symbol}</td><td>${it.tf}</td><td>${it.side||it.signal}</td><td>${it.score??''}</td><td>${it.entry??''}</td>`;
        tb.appendChild(tr);
      });
      $('#flux-table').style.display='table';
    }catch(e){
      $('#flux-err').style.display='block';
    }
  }

  // Heatmap
  async function loadHeat(){
    $('#heat-err').style.display='none';
    try{
      const r = await fetch('/heatmap?ts='+Date.now(), {cache:'no-store'});
      if(!r.ok) throw new Error();
      const j = await r.json();
      const cells = Array.isArray(j.cells)? j.cells : [];
      const wrap = $('#heat-wrap'); wrap.innerHTML='';
      if(!cells.length){ wrap.textContent='(vide)'; return; }
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

  // go
  showVersionAndMaybeUpdate();
  loadFlux(); loadHeat();
  setInterval(loadFlux, 20_000);
  setInterval(loadHeat, 60_000);
})();
