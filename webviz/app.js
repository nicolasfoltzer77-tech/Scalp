/* rtviz-ui refresh wiring */

const el = {
  ver: document.getElementById('uiVer'),
  grid: document.getElementById('grid'),
  msg: document.getElementById('msg'),
  btn: document.getElementById('btnRefresh'),
};

const STATUS_COLOR = { fresh: 'green', reloading: 'orange', stale: 'red', absent: 'gray' };

async function getJSON(path) {
  const url = `${path}?ts=${Date.now()}`;            // anti-cache
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) {
    const txt = await res.text().catch(()=>'');
    throw new Error(`${res.status} ${res.statusText} ${txt}`.trim());
  }
  return res.json();
}

function renderGrid(data) {
  // data = { tfs: ["1m","5m","15m"], items: [{symbol, tfs:{'1m':{status},...}}] }
  const { tfs, items } = data;
  const th = `
    <div class="row head">
      <div class="cell sym">Symbol</div>
      ${tfs.map(tf => `<div class="cell tf">${tf}</div>`).join('')}
    </div>`;
  const rows = (items || []).map(it => {
    const dots = tfs.map(tf => {
      const st = it.tfs?.[tf]?.status || 'absent';
      const cls = STATUS_COLOR[st] || 'gray';
      return `<div class="cell dot"><span class="dot ${cls}"></span></div>`;
    }).join('');
    return `<div class="row">
      <div class="cell sym">${it.symbol}</div>${dots}
    </div>`;
  }).join('');
  el.grid.innerHTML = th + rows;
}

function setBusy(busy, text='') {
  el.btn.disabled = busy;
  el.btn.textContent = busy ? 'Mise à jour…' : 'Mettre à jour';
  el.msg.textContent = text;
  el.msg.className = 'msg' + (text ? ' show' : '');
}

async function refreshAll() {
  try {
    setBusy(true, '');
    // version
    const v = await getJSON('/version');             // {ui:"1.0.xx"}
    el.ver.textContent = v.ui || '?';
    // data
    const data = await getJSON('/data');             // 200 -> JSON prêt
    renderGrid(data);
  } catch (e) {
    console.error(e);
    el.msg.textContent = "Impossible de charger les données.";
    el.msg.className = 'msg error show';
  } finally {
    setBusy(false);
  }
}

// bouton -> force refresh immédiat
el.btn?.addEventListener('click', refreshAll);

// premier chargement
refreshAll();

// (optionnel) auto-refresh toutes les 30s
// setInterval(refreshAll, 30000);
