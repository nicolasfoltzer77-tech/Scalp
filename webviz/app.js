(() => {
  const $=(s,p=document)=>p.querySelector(s); const $$=(s,p=document)=>p.querySelectorAll(s);

  $$('.tab').forEach(b=>b.onclick=()=>{
    $$('.tab').forEach(x=>x.classList.remove('active')); b.classList.add('active');
    const t=b.dataset.tab;
    $('#pane-flux').style.display=(t==='flux')?'block':'none';
    $('#pane-heatmap').style.display=(t==='heatmap')?'block':'none';
    $('#pane-hist').style.display=(t==='hist')?'block':'none';
  });

  async function showVersion(){
    try{
      const r = await fetch('/version?ts='+Date.now(), {cache:'no-store'});
      const {ui} = await r.json();
      $('#ui-ver').textContent = ui || '(?)';
    }catch{ $('#ui-ver').textContent='(?)'; }
  }

  const btn=$('#btn-update');
  btn.onclick=()=>{
    const u = new URL(location.href);
    u.searchParams.set('v', Date.now());  // cache-bust total
    location.replace(u.toString());
  };

  async function loadFlux(){
    $('#flux-err').style.display='none';
    try{
      const r = await fetch('/signals?ts='+Date.now(), {cache:'no-store'});
      if(!r.ok) throw 0;
      const arr = await r.json();
      const tb = $('#flux-table tbody'); tb.innerHTML='';
      (arr.slice(0,50)).forEach(it=>{
        const tr=document.createElement('tr');
        tr.innerHTML = `<td>${it.ts}</td><td>${it.sym||it.symbol}</td><td>${it.tf}</td><td>${it.side||it.signal}</td><td>${it.score??''}</td><td>${it.entry??''}</td>`;
        tb.appendChild(tr);
      });
      $('#flux-table').style.display='table';
    }catch{ $('#flux-err').style.display='block'; }
  }

  async function loadHeat(){
    $('#heat-err').style.display='none';
    try{
      const r = await fetch('/heatmap?ts='+Date.now(), {cache:'no-store'});
      if(!r.ok) throw 0;
      const j = await r.json();
      const cells = Array.isArray(j.cells)? j.cells : [];
      const wrap=$('#heat-wrap'); wrap.innerHTML='';
      if(!cells.length){ wrap.textContent='(vide)'; return; }
      const m={};
      cells.forEach(c=>{
        const s=(c.sym||c.symbol||'').toUpperCase(), tf=(c.tf||'').toLowerCase();
        if(!m[s]) m[s]={}; m[s][tf]=c.side||c.signal||'';
      });
      const t=document.createElement('table');
      t.innerHTML=`<thead><tr><th>sym \\ tf</th><th>1m</th><th>5m</th><th>15m</th></tr></thead><tbody></tbody>`;
      Object.keys(m).sort().forEach(s=>{
        const tr=document.createElement('tr');
        tr.innerHTML=`<td>${s}</td><td>${m[s]['1m']||''}</td><td>${m[s]['5m']||''}</td><td>${m[s]['15m']||''}</td>`;
        t.querySelector('tbody').appendChild(tr);
      });
      wrap.appendChild(t);
    }catch{ $('#heat-err').style.display='block'; }
  }

  showVersion(); loadFlux(); loadHeat();
  setInterval(loadFlux, 20000);
  setInterval(loadHeat, 60000);
})();
