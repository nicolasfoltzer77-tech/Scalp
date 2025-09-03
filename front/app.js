const $ = (s)=>document.querySelector(s);
document.querySelectorAll('nav button').forEach(b=>{
  b.onclick=()=>{
    document.querySelectorAll('nav button,.tab').forEach(x=>x.classList.remove('on'));
    b.classList.add('on'); $('#'+b.dataset.tab).classList.add('on');
  };
});

async function jget(u){ const r=await fetch(u,{headers:{'Accept':'application/json'}}); return r.json(); }

(async()=>{
  try{
    const meta = await jget('/test');           // <- doit renvoyer JSON via le proxy
    $('#api').textContent = 'API OK '+JSON.stringify(meta);
  }catch(e){ $('#api').textContent = 'API FAIL '+e; }

  // Exemples de sondes (si tes endpoints existent)
  try{ $('#flux-pre').textContent = JSON.stringify(await jget('/viz/flux?limit=5'),null,2); }catch{}
  try{ $('#heatmap-pre').textContent = JSON.stringify(await jget('/viz/heatmap'),null,2); }catch{}
  try{ $('#hist-pre').textContent = JSON.stringify(await jget('/viz/history?limit=5'),null,2); }catch{}
})();
