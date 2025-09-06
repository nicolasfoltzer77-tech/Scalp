async function getJSON(u){ const r=await fetch(u,{cache:'no-store'}); if(!r.ok) throw new Error(r.status); return r.json(); }

async function showVersion(){
  try{
    const v = await getJSON('/version');
    document.getElementById('ver').textContent = `rtviz-ui ${v.ui}`;
  }catch{ document.getElementById('ver').textContent = 'rtviz-ui ?'; }
}

async function loadData(){
  const panel = document.getElementById('panel');
  try{
    const js = await getJSON('/data');
    panel.textContent = '';
    const pre = document.createElement('pre');
    pre.textContent = JSON.stringify(js, null, 2);
    panel.appendChild(pre);
  }catch(e){
    panel.textContent = 'Données indisponibles.';
  }
}

document.addEventListener('DOMContentLoaded', ()=>{
  showVersion();
  loadData();

  document.getElementById('btn-update').addEventListener('click', ()=>{
    // force reload des ressources
    showVersion();
    loadData();
  });

  // onglets (visuel uniquement pour le moment)
  document.querySelectorAll('.tab').forEach(b=>{
    b.addEventListener('click', ()=>{
      document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
      b.classList.add('active');
      const t = b.dataset.tab;
      if(t==='data') loadData();
    });
  });
});
