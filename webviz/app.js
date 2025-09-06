// helpers
const $ = (s, p=document) => p.querySelector(s);

// version & bouton
async function loadVersion() {
  try {
    const j = await fetch('/version', {cache:'no-store'}).then(r=>r.json());
    $('#ver').textContent = `rtviz-ui ${j.ui || '—'}`;
  } catch { $('#ver').textContent = 'rtviz-ui ?'; }
}
$('#btn-update').addEventListener('click', () => {
  const u = new URL(location.href);
  u.searchParams.set('v', Date.now());
  location.replace(u.toString());
});

// mapping status -> couleur
const S2C = { fresh:'fresh', reloading:'reloading', stale:'stale', absent:'absent' };
const tfsDefault = ['1m','5m','15m'];

// rendu skeleton initial
function renderSkeleton(tfs=tfsDefault, rows=8) {
  let h = '<table><thead><tr><th>Symbol</th>';
  for (const tf of tfs) h += `<th>${tf}</th>`;
  h += '</tr></thead><tbody>';
  for (let i=0;i<rows;i++) {
    h += '<tr class="sk"><td>…</td>' + tfs.map(_=>'<td class="dotcell"><span class="pill absent"></span></td>').join('') + '</tr>';
  }
  h += '</tbody></table>';
  $('#panel').innerHTML = h;
}

// rendu tableau
function buildTable(data) {
  const tfs = data.tfs && Array.isArray(data.tfs) ? data.tfs : tfsDefault;
  let html = '<table><thead><tr><th>Symbol</th>';
  for (const tf of tfs) html += `<th>${tf}</th>`;
  html += '</tr></thead><tbody>';

  for (const it of (data.items||[])) {
    html += `<tr><td>${it.symbol}</td>`;
    for (const tf of tfs) {
      const st = (it.tfs?.[tf]?.status) || 'absent';
      html += `<td class="dotcell"><span class="pill ${S2C[st]||'absent'}" title="${st}"></span></td>`;
    }
    html += '</tr>';
  }
  html += '</tbody></table>';
  const ts = (data.updated_at? new Date(data.updated_at*1000): new Date());
  html += `<p class="muted">Mise à jour : ${ts.toLocaleString()}</p>`;
  return html;
}

async function loadData() {
  try {
    const j = await fetch('/data', {cache:'no-store'}).then(r=>{
      if(!r.ok) throw new Error(r.statusText); return r.json();
    });
    $('#panel').innerHTML = buildTable(j);
  } catch (e) {
    // garde les pastilles + skeleton si erreur
    renderSkeleton();
    const p = document.createElement('p');
    p.className='err'; p.textContent="Impossible de charger les données.";
    $('#panel').appendChild(p);
  }
}

// init + polling
loadVersion();
renderSkeleton();        // pastilles visibles tout de suite + skeleton
loadData();
setInterval(loadData, 5000);
