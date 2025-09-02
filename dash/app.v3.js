const $ = (s, p=document) => p.querySelector(s);
const fmt2 = n => (n==null ? "—" : Number(n).toLocaleString("fr-FR",{minimumFractionDigits:2,maximumFractionDigits:2}));
const fmtTime = iso => { try { return new Date(iso).toTimeString().slice(0,8);} catch { return "—"; } };

async function jget(url){ const r = await fetch(url,{cache:"no-store"}); if(!r.ok) throw new Error(url); return r.json(); }

function rowSignal(s){
  const base = (s.symbol||"").replace("USDT","").replace(/USDC|USD$/,"");
  const side = (s.side||"").toUpperCase();
  const cls = side==="BUY" ? "buy" : "sell";
  return `<tr>
    <td>${fmtTime(s.ts)}</td>
    <td><span class="badge ${cls}">${base||"—"}</span></td>
    <td class="muted">${side||"—"}</td>
    <td>${s.score?.toFixed?.(2) ?? "—"}</td>
    <td>${fmt2(s.qty_usdt ?? s.qty ?? 0)}</td>
    <td>${fmt2(s.risk?.sl ?? s.sl ?? 0)}</td>
    <td>${fmt2(Array.isArray(s.risk?.tp)?s.risk.tp[0]:(s.tp ?? 0))}</td>
  </tr>`;
}

function rowPosition(p, pxNow){
  const base = (p.symbol||"").replace("USDT","").replace(/USDC|USD$/,"");
  const side = (p.side||"LONG").toUpperCase();
  const cls = side==="LONG" ? "buy" : "sell";
  const entry = p.entry_price ?? p.entry ?? 0;
  const qty = p.qty_usdt ?? p.qty ?? 0;
  const pnl = (pxNow && entry) ? (side==="LONG" ? (pxNow-entry) : (entry-pxNow)) : 0;
  return `<tr>
    <td>${fmtTime(p.ts)}</td>
    <td class="muted">—</td>
    <td><span class="badge ${cls}">${base||"—"}</span></td>
    <td class="muted">${side}</td>
    <td>${fmt2(entry)}</td>
    <td>${fmt2(qty)}</td>
    <td>${fmt2(pnl)}</td>
  </tr>`;
}

async function refresh(){
  try{
    const [state, sigs, poss] = await Promise.all([
      jget("/api/state"),
      jget("/api/signals"),
      jget("/api/positions"),
    ]);

    // header pills
    $("#mode-pill").classList.toggle("active", (state.mode||"paper")==="real");
    for(const lvl of [1,2,3]){
      $("#risk-"+lvl).classList.toggle("active", state.risk_level==lvl);
    }

    // signals
    const sigRows = (sigs||[]).slice(0,20).map(rowSignal).join("") || `<tr><td colspan="7">—</td></tr>`;
    $("#tbody-signals").innerHTML = sigRows;

    // positions (need quote to compute PnL)
    let pxNow = 0;
    const sym0 = (poss?.[0]?.symbol)||"";
    if(sym0){
      try{
        const q = await jget(`/api/quotes?symbols=${encodeURIComponent(sym0)}`);
        pxNow = q?.[0]?.last ?? 0;
      }catch{}
    }
    const posRows = (poss||[]).slice(0,20).map(p=>rowPosition(p,pxNow)).join("") || `<tr><td colspan="7">—</td></tr>`;
    $("#tbody-positions").innerHTML = posRows;

    // heatmap (optional if backend not ready)
    try{
      const hm = await jget("/api/heatmap");
      const root = $("#heatmap");
      root.innerHTML = "";
      (hm.items||[]).slice(0,30).forEach(x=>{
        const div = document.createElement("div");
        const base = (x.base||x.sym||"").replace("USDT","");
        const cls = (x.ret||x.delta||0) >= 0 ? "green" : "red";
        div.className = `cell ${cls}`;
        div.textContent = base;
        root.appendChild(div);
      });
    }catch{/* ignore */}
  }catch(e){
    // show blanks
    $("#tbody-signals").innerHTML = `<tr><td colspan="7">—</td></tr>`;
    $("#tbody-positions").innerHTML = `<tr><td colspan="7">—</td></tr>`;
  }
}

setInterval(refresh, 2000);
refresh();
