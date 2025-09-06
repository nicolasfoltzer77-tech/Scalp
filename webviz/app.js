// --- util
const $ = (s, p=document) => p.querySelector(s);

// version & bouton
async function loadVersion() {
  try {
    const j = await fetch('/version', {cache:'no-store'}).then(r=>r.json());
    $('#ver').textContent = `rtviz-ui ${j.ui || '—'}`;
  } catch {
    $('#ver').textContent = 'rtviz-ui ?';
  }
}
$('#btn-update').addEventListener('click', () => {
  // recharge l’app en forçant le cache-busting
  const u = new URL(location.href);
  u.searchParams.set('v', Date.now());
  location.replace(u.toString());
});

// mapping statut -> classe couleur
const S2C = { fresh:'fresh', reloading:'reloading', stale:'stale', absent:'absent' };

// rend une cellule pastille
function dot(status) {
  const cls = S2C[status] || 'absent';
  return `<span class="pill ${cls}" title="${status}"></span>`;
}

function buildTable(data) {
  const tfs = data.tfs || ['1m','5m','15m'];
  let html = '<table><thead><tr><th>Symbol</th>';
  for (const tf of tfs) html += `<th>${tf}</th>`;
  html += '</tr></thead><tbody>';

  for (const it of (data.items||[])) {
    html += `<tr><td>${it.symbol}</td>`;
    for (const tf of tfs) {
      const st = (it.tfs?.[tf]?.status) || 'absent';
      html += `<td class="dotcell">${dot(st)}</td>`;
    }
    html += '</tr>';
  }
  html += '</tbody></table>';
  html += `<p class="muted">Mise à jour : ${new Date((data.updated_at||Date.now())*1000).toLocaleString()}</p>`;
  return html;
}

async function loadData() {
  try {
    const j = await fetch('/data', {cache:'no-store'}).then(r=>{
      if(!r.ok) throw new Error(r.statusText); return r.json();
    });
    $('#panel').innerHTML = buildTable(j);
  } catch (e) {
    $('#panel').innerHTML = `<p class="err">Impossible de charger les données.</p>`;
  }
}

// init + polling
loadVersion();
loadData();
setInterval(loadData, 5000);
