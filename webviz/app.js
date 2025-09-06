(async function(){
  const $ = (q)=>document.querySelector(q);
  const verEl = $("#ver");
  const tbody = $("#tbl tbody");
  const btn   = $("#refresh");
  const last10= $("#last10");

  const color = (s)=> s==="fresh" ? "green" : s==="reloading" ? "orange" : s==="stale" ? "red" : "grey";
  const dot = (s)=>`<span class="dot ${color(s)}"></span>`;

  async function getJSON(u){
    const r = await fetch(u,{cache:"no-store"});
    if(!r.ok) throw new Error(u+" -> "+r.status);
    return r.json();
  }

  async function tick(){
    try{
      try{ const v = await getJSON("/api/version"); verEl.textContent = (v.ui||"1.0.31"); }catch{}

      const st = await getJSON("/api/data-status");
      tbody.innerHTML = (st.items||[]).map(it=>{
        const sym = (it.symbol||"").toUpperCase().replace(/USDT$/,'');
        const s1 = it.tfs?.["1m"]?.status  || "absent";
        const s5 = it.tfs?.["5m"]?.status  || "absent";
        const s15= it.tfs?.["15m"]?.status || "absent";
        return `<tr><td>${sym}</td><td class="c">${dot(s1)}</td><td class="c">${dot(s5)}</td><td class="c">${dot(s15)}</td></tr>`;
      }).join("");

      const l10 = await getJSON("/api/last10-data").catch(()=>({}));
      last10.textContent = Array.isArray(l10)
        ? l10.map(x => `${(x.name||'').padEnd(26)}  ${x.mtime||''}  ${x.size??''}`).join("\n")
        : "—";
    }catch(e){
      last10.textContent = "Erreur "+e.message;
    }
  }

  document.getElementById("refresh").addEventListener("click", tick);
  tick(); setInterval(tick, 10_000);
})();
