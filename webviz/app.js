(async function(){
  const $=q=>document.querySelector(q);
  const verEl=$("#ver"), tbody=$("#tbl tbody"), last10=$("#last10");

  const color=s=>s==="fresh"?"green":s==="reloading"?"orange":s==="stale"?"red":"grey";
  const dot=s=>`<span class="dot ${color(s)}"></span>`;

  async function getJSON(url){
    const r=await fetch(url,{cache:"no-store"}); if(!r.ok) throw new Error(url+"->"+r.status);
    return r.json();
  }

  async function tick(){
    try{
      // version backend (fallback si API muette)
      try{ const v=await getJSON("/api/version"); verEl.textContent=v.ui||"1.0.31"; }
      catch{ verEl.textContent="1.0.31"; }

      // statut données
      const st=await getJSON("/api/data-status"); // {items:[...]}
      tbody.innerHTML=st.items.map(it=>{
        const sym=(it.symbol||"").toUpperCase().replace(/USDT$/,'');
        const s1=it.tfs?.["1m"]?.status||"absent";
        const s5=it.tfs?.["5m"]?.status||"absent";
        const s15=it.tfs?.["15m"]?.status||"absent";
        return `<tr class="row"><td>${sym}</td><td class="c">${dot(s1)}</td><td class="c">${dot(s5)}</td><td class="c">${dot(s15)}</td></tr>`;
      }).join("");

      // liste 10 derniers json/jsonl
      const l10=await getJSON("/api/last10-data").catch(()=>[]);
      last10.textContent = Array.isArray(l10)&&l10.length
        ? l10.map(x=>`${(x.name||"").padEnd(26)}  ${(x.mtime||"").padEnd(19)}  ${x.size??""}`).join("\n")
        : "—";
    }catch(e){ last10.textContent="Erreur "+e.message; }
  }

  $("#refresh")?.addEventListener("click", tick);
  tick(); setInterval(tick,10_000);
})();
