// Anti-clignotement solde : conserve dernier si delta <5s
let lastBalance = null;

async function fetchJSON(url) {
  try {
    const r = await fetch(url + '?t=' + Date.now());
    if (!r.ok) return null;
    return await r.json();
  } catch { return null; }
}

function pill(sig) {
  if (sig==="BUY") return '<span class="pill b">BUY</span>';
  if (sig==="SELL") return '<span class="pill s">SELL</span>';
  return '<span class="pill h">HOLD</span>';
}

function scoreCell(val){
  let cls="neu"; if(val>0) cls="pos"; if(val<0) cls="neg";
  return `<span class="score ${cls}">${val}</span>`;
}

async function refresh() {
  // solde
  const bal = await fetchJSON('/bitget_balance.json');
  if (bal && bal.equity_usdt) {
    const ts = new Date(bal.generated_at || Date.now());
    if (!lastBalance || Date.now()-new Date(lastBalance.ts) > 5000) {
      lastBalance = { val: bal.equity_usdt, ts };
    }
    document.getElementById('bitget').textContent = `Bitget: ${lastBalance.val}`;
    document.getElementById('bitget-ts').textContent = ts.toISOString().slice(11,19);
    document.getElementById('online').style.background = "var(--ok)";
  }

  // heatmap
  const signals = await fetchJSON('/signals.json');
  const hb = document.getElementById('heatBody');
  if (!signals || !signals.length) {
    hb.innerHTML = `<tr><td colspan=4 class=empty>Aucun signal</td></tr>`;
  } else {
    const grouped = {};
    signals.forEach(s=>{
      if(!grouped[s.symbol]) grouped[s.symbol]={};
      grouped[s.symbol][s.tf]=s;
    });
    hb.innerHTML = Object.entries(grouped).map(([sym,tfs])=>{
      return `<tr class="hm-row" data-sym="${sym}">
        <td class="symbol">${sym}</td>
        <td class="cell">${pill(tfs["1m"]?.signal)}${scoreCell(tfs["1m"]?.score||0)}</td>
        <td class="cell">${pill(tfs["5m"]?.signal)}${scoreCell(tfs["5m"]?.score||0)}</td>
        <td class="cell">${pill(tfs["15m"]?.signal)}${scoreCell(tfs["15m"]?.score||0)}</td>
      </tr>`;
    }).join("");
    hb.querySelectorAll(".hm-row").forEach(tr=>{
      tr.onclick = ()=>showDetail(tr.dataset.sym,grouped[tr.dataset.sym]);
    });
  }

  // positions
  const pos = await fetchJSON('/positions.json');
  const pb = document.getElementById('posBody');
  if (!pos || !pos.length) {
    pb.innerHTML = `<tr><td colspan=7 class=empty>—</td></tr>`;
  } else {
    pb.innerHTML = pos.map(p=>{
      let pnlCls = p.pnl>0?"pos":p.pnl<0?"neg":"neu";
      return `<tr>
        <td>${p.open_time||""}</td><td>${p.symbol}</td><td>${p.side}</td>
        <td>${p.qty}</td><td>${p.entry||""}</td><td>${p.exit||""}</td>
        <td class="${pnlCls}">${p.pnl}</td></tr>`;
    }).join("");
  }
}

// détail = tableau 3 colonnes (1m/5m/15m)
function showDetail(sym,tfs){
  const dp=document.getElementById('detailPanel');
  document.getElementById('dp-title').textContent=`Sous-stratégies — ${sym}`;
  const allStrats=["sma_cross_fast","rsi_reversion","ema_trend"];
  let html="<table><thead><tr><th>Sous-strat</th><th>1m</th><th>5m</th><th>15m</th></tr></thead><tbody>";
  allStrats.forEach(st=>{
    html+=`<tr><td>${st}</td>
      <td>${pill(tfs["1m"]?.sub?.[st]||"HOLD")}</td>
      <td>${pill(tfs["5m"]?.sub?.[st]||"HOLD")}</td>
      <td>${pill(tfs["15m"]?.sub?.[st]||"HOLD")}</td>
    </tr>`;
  });
  html+="</tbody></table>";
  document.getElementById('dp-content').innerHTML=html;
  dp.style.display="block";
}
document.getElementById('dp-close').onclick=()=>document.getElementById('detailPanel').style.display="none";

setInterval(refresh,4000);
refresh();
