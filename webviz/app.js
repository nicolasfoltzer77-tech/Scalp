const $ = sel => document.querySelector(sel);
const table = $("#table");
const msg = $("#errmsg");
const uiSpan = $("#ui");
const lastBody = $("#lastjson");
const lastEmpty = $("#lastjson-empty");
const btn = $("#btnRefresh");

const STATE_COLORS = { fresh:"green", reloading:"orange", stale:"red", absent:"gray" };

async function fetchJSON(url){
  const r = await fetch(url, {cache:"no-store"});
  if(!r.ok) throw new Error(`${url} -> ${r.status}`);
  return await r.json();
}

function renderData(data){
  // data = {tfs:["1m","5m","15m"], min_candles:1500, items:[{symbol,...}]}
  const tfs = data.tfs || ["1m","5m","15m"];
  const head = `
    <div class="row head">
      <div class="cell sym">Symbol</div>
      ${tfs.map(tf => `<div class="cell tf">${tf}</div>`).join("")}
    </div>`;
  const rows = (data.items || []).map(it => {
    const cells = tfs.map(tf => {
      const st = it.tfs?.[tf]?.status || "absent";
      const dot = `<span class="dot ${STATE_COLORS[st]||"gray"}"></span>`;
      return `<div class="cell tf"><span class="cell dot">${dot}</span></div>`;
    }).join("");
    return `<div class="row"><div class="cell sym">${it.symbol||"?"}</div>${cells}</div>`;
  }).join("");
  table.innerHTML = head + rows;
}

function setError(show, text){
  msg.textContent = text || "Impossible de charger les données.";
  msg.classList.toggle("show", !!show);
}

async function refreshAll(manual=false){
  try{
    const [ver, data] = await Promise.all([
      fetchJSON("/version"),
      fetchJSON("/data")
    ]);
    uiSpan.textContent = `rtviz-ui ${ver.ui||"?"}`;
    renderData(data);
    setError(false);
  }catch(e){
    setError(true, "Impossible de charger les données.");
  }
  try{
    const last = await fetchJSON("/logs/last10data");
    renderLast(last);
  }catch(e){
    renderLast([]);
  }
  if(manual){
    // petit flash visuel si tu veux plus tard
  }
}

function renderLast(arr){
  if(!Array.isArray(arr) || arr.length===0){
    lastBody.innerHTML = "";
    lastEmpty.style.display = "block";
    return;
  }
  lastEmpty.style.display = "none";
  lastBody.innerHTML = arr.map(x=>{
    const size = Number(x.size||0);
    const human = size>1e6 ? (size/1e6).toFixed(2)+" MB" :
                 size>1e3 ? (size/1e3).toFixed(1)+" kB" : size+" B";
    return `<tr>
      <td style="padding:4px">${x.name||""}</td>
      <td style="padding:4px">${x.mtime||""}</td>
      <td style="padding:4px;text-align:right">${human}</td>
    </tr>`;
  }).join("");
}

// actions
btn?.addEventListener("click", ()=>refreshAll(true));

// tick auto 10s
refreshAll();
setInterval(refreshAll, 10_000);
