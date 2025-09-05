/* rtviz-ui 1.0.2 → 1.0.4  (Data: only pills + legend, no timers) */
const POLL_MS = 10000;

async function j(url){const r=await fetch(url,{cache:"no-store"});if(!r.ok)throw new Error(r.status+" "+r.statusText);return r.json();}

function pill(status){
  const span=document.createElement("span");
  span.className="pill";
  let bg="#1b1b1b", br="#333", txt="absent";
  if(status==="fresh"){bg="#0b1220";br="#223043";txt="fresh";}
  else if(status==="reloading"){bg="#3a2a12";br="#684a1a";txt="reloading";}
  else if(status==="stale"){bg="#2a0f0f";br="#5a1b1b";txt="stale";}
  span.style.background=bg; span.style.borderColor=br;
  span.textContent = txt;
  return span;
}

function legend(){
  const wrap=document.createElement("div");
  wrap.style.display="flex"; wrap.style.gap="8px"; wrap.style.marginBottom="8px";
  const variants = [
    ["fresh","#0b1220","#223043"],
    ["reloading","#3a2a12","#684a1a"],
    ["stale","#2a0f0f","#5a1b1b"],
    ["absent","#1b1b1b","#333"]
  ];
  variants.forEach(([txt,bg,br])=>{
    const p=document.createElement("span");
    p.className="pill"; p.style.background=bg; p.style.borderColor=br; p.textContent=txt;
    wrap.appendChild(p);
  });
  return wrap;
}

// -------- DATA TAB ----------
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
    ["Symbol",...d.tfs].forEach(h=>{const th=document.createElement("th");th.textContent=h;trh.appendChild(th);});
    thead.appendChild(trh); t.appendChild(thead);

    const tb=document.createElement("tbody");
    d.items.forEach(row=>{
      const tr=document.createElement("tr");
      const td0=document.createElement("td"); td0.textContent=row.symbol; tr.appendChild(td0);
      d.tfs.forEach(tf=>{
        const td=document.createElement("td");
        const st=(row.tfs?.[tf]?.status)||"absent";
        td.appendChild(pill(st));
        tr.appendChild(td);
      });
      tb.appendChild(tr);
    });
    t.appendChild(tb);
    root.appendChild(t);

    const upd=document.createElement("div");
    upd.className="muted"; upd.style.marginTop="8px";
    upd.textContent="Mise à jour OK";
    root.appendChild(upd);
  }catch(e){
    root.innerHTML=`<div class="err">Erreur de chargement: ${e}</div>`;
  }
}

// -------- TABS / NAV ----------
function selectTab(name){
  document.querySelectorAll(".panel").forEach(p=>p.style.display="none");
  document.getElementById(`tab-${name}`).style.display="block";
  document.querySelectorAll(".tab-btn").forEach(b=>b.classList.remove("active"));
  document.querySelector(`[data-tab="${name}"]`).classList.add("active");

  clearInterval(DATA_TIMER);
  if(name==="data"){
    loadData();
    DATA_TIMER=setInterval(loadData, POLL_MS);
  }
}

async function showVer(){
  try{const v=await j("/version"); document.getElementById("ver").textContent=`rtviz-ui ${v.ui}`;}
  catch{ document.getElementById("ver").textContent=`rtviz-ui`; }
}
function doUpdate(){ location.href='/?v='+(Date.now()%100000); }

window.addEventListener("DOMContentLoaded", ()=>{
  document.getElementById("btn-update").addEventListener("click", doUpdate);
  document.querySelectorAll(".tab-btn").forEach(b=>b.addEventListener("click",()=>selectTab(b.dataset.tab)));
  showVer();
  selectTab("data"); // Data en premier
});
