(function(){
  const $ = s => document.querySelector(s);
  const statusFlux = $("#flux-status"), statusHeat = $("#heatmap-status");
  const errFlux = $("#flux-error"), errHeat = $("#heatmap-error"), errHist = $("#history-error");

  async function j(path){
    const r = await fetch(path, {cache:"no-store"});
    if(!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    return r.json();
  }

  // ---- Tabs
  document.querySelectorAll(".tab").forEach(t=>{
    t.onclick = ()=>{
      document.querySelectorAll(".tab").forEach(x=>x.classList.remove("active"));
      t.classList.add("active");
      const id = t.dataset.tab;
      ["flux","heatmap","history"].forEach(n => {
        $("#panel-"+n).hidden = (n!==id);
      });
    };
  });

  // ---- FLUX ----
  async function loadFlux(){
    errFlux.textContent="";
    statusFlux.textContent = "Flux: …";
    try{
      const rows = await j("/signals");
      statusFlux.textContent = `Flux: OK (${rows.length})`;
      const tb = $("#flux-body"); tb.innerHTML="";
      rows.slice(0,200).forEach(r=>{
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${r.ts??""}</td><td>${r.sym??r.symbol??""}</td><td>${r.tf??""}</td>
                        <td>${(r.side||r.signal||"").toString()}</td>
                        <td>${r.rsi??""}</td><td>${r.sma??""}</td><td>${r.ema??""}</td><td>${r.score??""}</td>`;
        tb.appendChild(tr);
      });
    }catch(e){
      statusFlux.textContent = "Flux: ERR";
      errFlux.textContent = "Erreur de chargement.";
    }
  }

  // ---- HEATMAP ----
  function cell(side){
    const s = (side||"").toString().toUpperCase();
    const d = document.createElement("div");
    d.className = "hcell heat-"+s;
    d.textContent = s==="BUY"?"B":s==="SELL"?"S":"H";
    d.style.display="inline-block";
    d.style.minWidth="36px"; d.style.textAlign="center";
    d.style.padding="6px 0"; d.style.margin="3px";
    d.style.borderRadius="8px"; d.style.border="1px solid #17202b";
    return d;
  }
  async function loadHeatmap(){
    errHeat.textContent=""; statusHeat.textContent="Heatmap: …";
    const grid = $("#heatmap-grid"); grid.innerHTML="";
    try{
      const hm = await j("/heatmap");
      // Formats acceptés :
      // A) {symbols:[], tfs:[], cells:[{sym:"BTCUSDT","1m":"H","5m":"BUY",...}, ...]}
      // B) {cells:[{sym:"BTCUSDT", tf:"1m", side:"HOLD"}, ...]}  (on reconstruit)
      let symbols = hm.symbols, tfs = hm.tfs, cells = hm.cells;

      if (!symbols || !tfs){
        // reconstruit à partir de B)
        const latest = {};
        (cells||[]).forEach(o=>{
          const s = o.sym||o.symbol||""; const tf = o.tf||""; const side = o.side||o.signal||"";
          if(!s||!tf) return;
          const key = s+"|"+tf;
          if(!latest[key] || (o.ts??0) > (latest[key].ts??0)) latest[key]=o;
        });
        symbols = Array.from(new Set(Object.keys(latest).map(k=>k.split("|")[0]))).sort();
        const order = ["1m","5m","15m","30m","1h","4h","1d"];
        tfs = Array.from(new Set(Object.keys(latest).map(k=>k.split("|")[1]))).sort((a,b)=> (order.indexOf(a)+999)%999 - (order.indexOf(b)+999)%999);
        cells = symbols.map(s=>{
          const row = {sym:s};
          tfs.forEach(tf=>{ row[tf] = (latest[s+"|"+tf]?.side || ""); });
          return row;
        });
      }

      // rendu
      const head = document.createElement("div");
      head.style.marginBottom="8px";
      head.innerHTML = `<div class="muted" style="margin-bottom:6px">sym \\ tf</div>`;
      grid.appendChild(head);
      symbols.forEach(s=>{
        const row = document.createElement("div");
        row.style.display="flex"; row.style.alignItems="center"; row.style.margin="4px 0";
        const label = document.createElement("div");
        label.textContent = s; label.style.width="140px"; label.style.color="#9fb0c6";
        row.appendChild(label);
        (tfs||[]).forEach(tf=>{
          const c = (cells.find(x=>x.sym===s)||{})[tf];
          row.appendChild(cell(c));
        });
        grid.appendChild(row);
      });

      statusHeat.textContent = `Heatmap: OK (${(cells||[]).length} lignes)`;
    }catch(e){
      statusHeat.textContent = "Heatmap: ERR";
      errHeat.textContent = "Erreur de chargement heatmap.";
    }
  }

  // ---- HISTORY (BTCUSDT) ----
  async function loadHistory(){
    errHist.textContent="";
    try{
      const rows = await j("/history/BTCUSDT");
      const tb = $("#history-body"); tb.innerHTML="";
      rows.slice(0,200).forEach(r=>{
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${r.ts??""}</td><td>${r.tf??""}</td><td>${(r.side||r.signal||"")}</td>
                        <td>${r.rsi??""}</td><td>${r.sma??""}</td><td>${r.ema??""}</td><td>${r.score??""}</td>`;
        tb.appendChild(tr);
      });
    }catch(e){
      errHist.textContent="Erreur de chargement historique.";
    }
  }

  // init
  loadFlux(); loadHeatmap(); loadHistory();
})();
