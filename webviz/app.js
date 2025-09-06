/* rtviz-ui app.js */
const $ = (s) => document.querySelector(s);

async function getJSON(u){
  const r = await fetch(u, {cache:"no-store"});
  if (!r.ok) throw new Error(`${u} -> ${r.status}`);
  return await r.json();
}

function dotClass(status){
  switch(status){
    case "fresh": return "cell-dot fresh";
    case "reloading": return "cell-dot reloading";
    case "stale": return "cell-dot stale";
    default: return "cell-dot absent";
  }
}

function renderTable(state){
  const tfs = state.tfs || ["1m","5m","15m"];
  let html = `<table><thead><tr><th>Symbol</th>${tfs.map(tf=>`<th>${tf}</th>`).join("")}</tr></thead><tbody>`;
  for (const it of state.items || []){
    html += `<tr><td>${it.symbol || "…"}</td>`;
    for (const tf of tfs){
      const s = it.tfs?.[tf]?.status || "absent";
      html += `<td><i class="${dotClass(s)}"></i></td>`;
    }
    html += `</tr>`;
  }
  html += `</tbody></table>`;
  $("#zone").innerHTML = html;
}

async function refreshAll(){
  $("#err").style.display="none";
  try{
    const v = await getJSON("/version");
    $("#ver").textContent = v.ui || "?.?.?";
  }catch(e){ /* version non bloquante */ }

  try{
    const data = await getJSON("/data");
    renderTable(data);
  }catch(e){
    $("#zone").innerHTML = "";
    $("#err").textContent = "Impossible de charger les données.";
    $("#err").style.display = "block";
  }
}

$("#btn").addEventListener("click", ()=> refreshAll());
refreshAll();
setInterval(refreshAll, 5000);
