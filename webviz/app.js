(async function(){
  const prefixes = ["", "/viz", "/api"];
  async function tryFetch(p, path){
    try{
      const r = await fetch(p + path, {cache:"no-store"});
      if (r.ok) return {ok:true, pfx:p, data: await r.json()};
    }catch(e){}
    return {ok:false};
  }
  async function detectPrefix(){
    for (const p of prefixes){
      const t = await tryFetch(p, "/hello");
      if (t.ok) return p;
    }
    return ""; // fallback
  }
  const PFX = await detectPrefix();
  // helpers
  async function getJSON(path){
    const r = await fetch(PFX + path, {cache:"no-store"});
    if (!r.ok) throw new Error(`${r.status}`);
    return r.json();
  }

  // Tabs (déjà dans index)
  const qs = s => document.querySelector(s);

  // ---- FLUX
  async function loadFlux(){
    const body = qs("#flux-body"), err = qs("#flux-error");
    body.innerHTML = ""; err.textContent = "";
    try{
      const rows = await getJSON("/signals");
      for (const r of rows.slice(0,200)){
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${r.ts}</td><td>${r.sym}</td><td>${r.tf}</td>
                        <td>${r.side}</td><td>${r.rsi||""}</td>
                        <td>${r.sma||""}</td><td>${r.ema||""}</td><td>${r.score||""}</td>`;
        body.appendChild(tr);
      }
    }catch(e){ err.textContent = "Erreur de chargement."; }
  }

  // ---- HEATMAP
  async function loadHeatmap(){
    const pre = qs("#heatmap-body"), err = qs("#heatmap-error");
    pre.textContent=""; err.textContent="";
    try{
      const data = await getJSON("/heatmap");
      pre.textContent = JSON.stringify(data,null,2);
    }catch(e){ err.textContent = "Erreur de chargement heatmap."; }
  }

  // ---- HISTORY (BTCUSDT)
  async function loadHistory(){
    const body = qs("#history-body"), err = qs("#history-error");
    body.innerHTML=""; err.textContent="";
    try{
      const rows = await getJSON("/history/BTCUSDT");
      for (const r of rows.slice(0,200)){
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${r.ts}</td><td>${r.tf}</td><td>${r.side}</td>
                        <td>${r.rsi||""}</td><td>${r.sma||""}</td><td>${r.ema||""}</td><td>${r.score||""}</td>`;
        body.appendChild(tr);
      }
    }catch(e){ err.textContent="Erreur de chargement historique."; }
  }

  // ---- DATA STATUS
  async function loadData(){
    const body = qs("#data-body"), err = qs("#data-error");
    if (!body) return;
    body.innerHTML=""; err.textContent="";
    try{
      const st = await getJSON("/data_status");
      const tfs = ["1m","5m","15m"];
      Object.keys(st).sort().forEach(sym=>{
        const tr = document.createElement("tr");
        const cells = tfs.map(tf=>{
          const o = st[sym]?.[tf];
          const state = o?.state || "missing";
          const cls = state==="fresh"?"green":state==="stale"?"red":state==="loading"?"orange":"grey";
          return `<td class="${cls}">${state}</td>`;
        }).join("");
        tr.innerHTML = `<td>${sym}</td>${cells}`;
        body.appendChild(tr);
      });
    }catch(e){ err.textContent="Erreur de chargement des statuts."; }
  }

  // chargement initial
  loadFlux(); loadHeatmap(); loadHistory(); loadData();
})();
