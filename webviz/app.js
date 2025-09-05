// ==== helpers =========================================================
const $ = (sel) => document.querySelector(sel);
const el = (tag, attrs={}, children=[]) => {
  const n = document.createElement(tag);
  Object.entries(attrs).forEach(([k,v]) => (k==="class"? n.className=v : n.setAttribute(k,v)));
  (Array.isArray(children)?children:[children]).forEach(c => n.append(c));
  return n;
};
function setPillState(sym, tf, state){
  const id = `pill-${sym}-${tf}`;
  const p = document.getElementById(id);
  if(!p) return;
  p.className = `pill ${state}`;
}

// ==== version + anti-cache ===========================================
async function loadVersion(){
  try{
    const r = await fetch("/version",{cache:"no-store"});
    const j = await r.json();
    $("#ver").textContent = `rtviz-ui ${j.ui}`;
  }catch(e){
    $("#ver").textContent = "rtviz-ui (indisponible)";
  }
}
$("#btn-update").onclick = () => {
  const u = new URL(window.location.href);
  u.searchParams.set("v", Date.now().toString());
  window.location.replace(u.toString());
};

// ==== tabs ============================================================
document.getElementById("tabs").addEventListener("click",(ev)=>{
  const b = ev.target.closest("button[data-tab]");
  if(!b) return;
  document.querySelectorAll(".tab").forEach(t=>t.classList.remove("active"));
  b.classList.add("active");
  const id = b.dataset.tab;
  ["data","flux","heatmap","history"].forEach(x=>{
    const sec = document.getElementById(`tab-${x}`);
    if(!sec) return;
    sec.hidden = (x!==id);
  });
});

// ==== Data grid =======================================================
function renderDataGrid(payload){
  const root = $("#data-root");
  if(!payload || !payload.symbols){
    root.innerHTML = '<div class="err">Pas de données reçues</div>';
    return;
  }
  const syms = payload.symbols;
  const t = el("table");
  const thead = el("thead",{},[
    el("tr",{},[
      el("th",{},["Symbol"]), el("th",{},["1m"]), el("th",{},["5m"]), el("th",{},["15m"])
    ])
  ]);
  const tb = el("tbody");
  Object.keys(syms).sort().forEach(sym=>{
    const row = syms[sym]||{};
    const tr = el("tr",{},[
      el("td",{},[sym]),
      el("td",{},[ el("i",{id:`pill-${sym}-1m`, class:`pill ${row["1m"]||"absent"}`}) ]),
      el("td",{},[ el("i",{id:`pill-${sym}-5m`, class:`pill ${row["5m"]||"absent"}`}) ]),
      el("td",{},[ el("i",{id:`pill-${sym}-15m`,class:`pill ${row["15m"]||"absent"}`}) ])
    ]);
    tb.append(tr);
  });
  t.append(thead,tb);
  root.replaceChildren(t);
}

async function refreshData(){
  try{
    const r = await fetch("/data",{cache:"no-store"});
    if(!r.ok) throw new Error("HTTP "+r.status);
    const j = await r.json();
    renderDataGrid(j);
  }catch(e){
    $("#data-root").innerHTML = `<div class="err">Erreur /data : ${e.message}</div>`;
  }
}
// toutes les 5s
setInterval(refreshData, 5000);

// ==== SSE (instantané pour 1m) ========
(function subscribeSSE(){
  try{
    const es = new EventSource("/data/stream");
    es.addEventListener("one_min_fresh",(evt)=>{
      const p = JSON.parse(evt.data); // {sym, tf:'1m', state:'fresh'}
      setPillState(p.sym,"1m","fresh");
    });
  }catch(e){}
})();

// ==== boot ============================================================
loadVersion();
refreshData();
