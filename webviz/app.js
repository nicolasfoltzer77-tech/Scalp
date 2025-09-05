/* rtviz-ui 1.0.4 -> 1.0.5 (color dots only) */
const POLL_MS = 10000;

async function j(u){const r=await fetch(u,{cache:"no-store"}); if(!r.ok)throw new Error(r.status); return r.json();}

function dot(status, title){
  const d=document.createElement("span");
  d.className="dot "+(status||"absent");
  if(title) d.title = title;
  return d;
}

function legend(){
  const l=document.createElement("div"); l.className="legend";
  l.innerHTML = `
    <span><span class="dot fresh"></span> <small>fresh</small></span>
    <span><span class="dot reloading"></span> <small>reloading</small></span>
    <span><span class="dot stale"></span> <small>stale</small></span>
    <span><span class="dot absent"></span> <small>absent</small></span>`;
  return l;
}

let DATA_TIMER=null;
async function loadData(){
  const root=document.getElementById("data-root");
  try{
    const d=await j("/data");
    root.innerHTML="";
    root.appendChild(legend());

    const t=document.createElement("table");
    const thead=document.createElement("thead");
    const trh=document.createElement("tr");
    ["Symbol", ...d.tfs].forEach(h=>{const th=document.createElement("th"); th.textContent=h; trh.appendChild(th);});
    thead.appendChild(trh); t.appendChild(thead);

    const tb=document.createElement("tbody");
    d.items.forEach(row=>{
      const tr=document.createElement("tr");
      const td0=document.createElement("td"); td0.textContent=row.symbol; tr.appendChild(td0);
      d.tfs.forEach(tf=>{
        const info=row.tfs?.[tf]||{status:"absent",candles:0};
        const td=document.createElement("td");
        const title=`${row.symbol} ${tf} · ${info.status} · ${info.candles} candles`;
        td.appendChild(dot(info.status, title));
        tr.appendChild(td);
      });
      tb.appendChild(tr);
    });
    t.appendChild(tb);
    root.appendChild(t);
  }catch(e){
    root.innerHTML = `<div class="err">Erreur de chargement: ${e}</div>`;
  }
}

function selectTab(name){
  document.querySelectorAll(".panel").forEach(p=>p.style.display="none");
  document.getElementById(`tab-${name}`).style.display="block";
  document.querySelectorAll(".tab-btn").forEach(b=>b.classList.remove("active"));
  const btn=document.querySelector(`[data-tab="${name}"]`); if(btn) btn.classList.add("active");

  clearInterval(DATA_TIMER);
  if(name==="data"){ loadData(); DATA_TIMER=setInterval(loadData, POLL_MS); }
}

async function showVer(){ try{const v=await j("/version"); document.getElementById("ver").textContent=`rtviz-ui ${v.ui}`;}catch{} }
function doUpdate(){ location.href='/?v='+(Date.now()%100000); }

window.addEventListener("DOMContentLoaded", ()=>{
  document.getElementById("btn-update")?.addEventListener("click", doUpdate);
  document.querySelectorAll(".tab-btn").forEach(b=>b.addEventListener("click",()=>selectTab(b.dataset.tab)));
  showVer(); selectTab("data");
});
