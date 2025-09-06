(async function(){
  const $ = (q)=>document.querySelector(q);
  const verEl = $("#ver");
  const tbody = $("#tbl tbody");
  const btn   = $("#refresh");
  const last10= $("#last10");

  const color = (status)=>{
    if(status==="fresh") return "green";
    if(status==="reloading") return "orange";
    if(status==="stale") return "red";
    return "grey";
  };
  const dot = (status)=>`<span class="dot ${color(status)}"></span>`;

  async function getJSON(url){
    const r = await fetch(url, {cache:"no-store"});
    if(!r.ok) throw new Error(url+" -> "+r.status);
    return r.json();
  }

  async function tick(){
    try{
      // version backend (facultatif)
      try{ const v = await getJSON("/api/version"); verEl.textContent = v.ui || ""; }catch{}
      // statut des données
      const st = await getJSON("/api/data-status");   // {items:[{symbol,tfs:{1m:{status},5m:{},15m:{}}}]}
      tbody.innerHTML = st.items.map(it=>{
        const sym = (it.symbol||"").toUpperCase().replace(/USDT$/,''); // ← retire USDT
        const s1 = it.tfs?.["1m"]?.status  || "absent";
        const s5 = it.tfs?.["5m"]?.status  || "absent";
        const s15= it.tfs?.["15m"]?.status || "absent";
        return `<tr>
          <td>${sym}</td>
          <td class="c">${dot(s1)}</td>
          <td class="c">${dot(s5)}</td>
          <td class="c">${dot(s15)}</td>
        </tr>`;
      }).join("");

      // liste des derniers fichiers
      const l10 = await getJSON("/api/last10-data").catch(()=>({}));
      if(Array.isArray(l10)){
        last10.textContent = l10.map(x =>
          `${x.name.padEnd(26)}  ${x.mtime}  ${x.size}`
        ).join("\n");
      }else{
        last10.textContent = "—";
      }
    }catch(e){
      last10.textContent = "Erreur "+e.message;
    }
  }

  $("#refresh").addEventListener("click", tick);
  tick(); setInterval(tick, 10_000);
})();
