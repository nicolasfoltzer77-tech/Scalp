(function(){
  const UI_VER="1.0.30";  // front
  document.getElementById('ui-ver').textContent = UI_VER;

  const API = (p)=>fetch(p,{headers:{'Accept':'application/json'}}).then(r=>r.json());
  const $ = (sel)=>document.querySelector(sel);

  function dot(cls){const i=document.createElement('i');i.className='dot '+cls;return i}
  function row(sym, m1, m5, m15){
    const r=document.createElement('div');r.className='row';
    const c1=document.createElement('div');c1.className='cell sym';c1.textContent=sym; r.append(c1);
    for(const m of [m1,m5,m15]){
      const c=document.createElement('div');c.className='cell dot';
      c.append(dot(m)); r.append(c);
    }
    return r;
  }
  function header(){
    const r=document.createElement('div');r.className='row head';
    ['Symbol','1m','5m','15m'].forEach(t=>{const d=document.createElement('div');d.textContent=t;d.className='cell tf';r.append(d)});
    return r;
  }

  // Status dots -> from /api/data-status (or fallback to heatmap)
  async function loadGrid(){
    const grid = $('#grid'); grid.innerHTML='';
    grid.append(header());
    try{
      const s = await API('/api/data-status'); // {items:[{sym, tfs:{'1m':'green','5m':'orange','15m':'gray'}}]}
      const items = s.items || [];
      for(const it of items){
        const t=it.tfs||{};
        grid.append(row(it.sym || it.symbol || '-', t['1m']||'gray', t['5m']||'gray', t['15m']||'gray'));
      }
      $('#msg').classList.remove('show');
    }catch(e){
      $('#msg').textContent='Erreur API /api/data-status'; $('#msg').classList.add('show');
    }
  }

  // Last 10 JSON/JSONL in /opt/scalp/data -> generated every 10s by last10data.service
  async function loadLast10(){
    const tb = document.querySelector('#last10 tbody'); tb.innerHTML='';
    try{
      const list = await API('/api/last10-data'); // [{name,path,size,mtime}]
      if(!Array.isArray(list) || list.length===0){
        tb.innerHTML='<tr><td colspan=3 class="muted">Aucun fichier .json trouvé.</td></tr>'; return;
      }
      for(const it of list){
        const tr=document.createElement('tr');
        const sz = typeof it.size==='number'? (it.size>=1024? (it.size/1024).toFixed(1)+'K': it.size+'B') : '';
        tr.innerHTML = `<td>${it.name}</td><td>${it.mtime||''}</td><td>${sz}</td>`;
        tb.appendChild(tr);
      }
    }catch(e){
      tb.innerHTML='<tr><td colspan=3 class="muted">Erreur /api/last10-data</td></tr>';
    }
  }

  function tick(){
    loadGrid();
    loadLast10();
  }
  tick(); setInterval(tick, 10000);
})();
