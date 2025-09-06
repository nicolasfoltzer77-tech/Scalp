async function fetchJSON(url){
  const r = await fetch(url);
  if(!r.ok) throw new Error(`${url} -> ${r.status}`);
  return r.json();
}

async function renderVersion(){
  try{
    const {ui} = await fetchJSON('/version');
    document.getElementById('ver').textContent = `rtviz-ui ${ui}`;
  }catch(e){
    document.getElementById('ver').textContent = '(version ?)';
  }
}

function pill(color){ const s=document.createElement('span'); s.className=`dot ${color}`; return s; }

function statusToColor(s){
  if(s==='fresh') return 'green';
  if(s==='reloading') return 'orange';
  if(s==='stale') return 'red';
  return 'gray';
}

async function renderData(){
  const host = document.getElementById('data');
  host.textContent = 'Chargement…';
  try{
    const d = await fetchJSON('/data');     // doit répondre côté backend
    // d = { tfs:["1m","5m","15m"], items:[ {symbol:"BTC", tfs:{ "1m":{status:"fresh"}, ...}} ] }
    const tfs = d.tfs || ["1m","5m","15m"];
    const table = document.createElement('table');
    table.style.width='100%'; table.style.borderCollapse='collapse';
    const thead = document.createElement('thead');
    thead.innerHTML = `<tr><th style="text-align:left">Symbol</th>${tfs.map(tf=>`<th>${tf}</th>`).join('')}</tr>`;
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    (d.items||[]).forEach(row=>{
      const tr = document.createElement('tr');
      const tdSym = document.createElement('td'); tdSym.textContent = row.symbol; tr.appendChild(tdSym);
      tfs.forEach(tf=>{
        const td = document.createElement('td'); td.style.textAlign='center';
        const st = row.tfs?.[tf]?.status || 'absent';
        td.appendChild(pill(statusToColor(st)));
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    host.replaceChildren(table);
  }catch(e){
    host.textContent = "Impossible de charger les données.";
  }
}

window.addEventListener('load', ()=>{
  document.getElementById('btn-refresh').onclick = ()=> location.reload(true);
  renderVersion();
  renderData();
  // rafraîchit les pastilles toutes les 15s sans recharger la page
  setInterval(renderData, 15000);
});
