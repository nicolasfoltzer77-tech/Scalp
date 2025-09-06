(async () => {
  const $ver = document.getElementById('ver');
  const $rows = document.getElementById('rows');
  const $err = document.getElementById('err');
  const $btn = document.getElementById('btn-refresh');

  const statusToClass = s => ({
    fresh: 'green',
    reloading: 'orange',
    stale: 'red',
    absent: 'gray'
  }[s] || 'gray');

  async function getJSON(url) {
    const r = await fetch(url, {cache:'no-store'});
    if (!r.ok) throw new Error(`${url} -> ${r.status}`);
    return r.json();
  }

  async function loadVersion() {
    try {
      const js = await getJSON('/version');
      $ver.textContent = `rtviz-ui ${js.ui}`;
    } catch (e) {
      console.error('version', e);
    }
  }

  function render(data) {
    $rows.innerHTML = '';
    const tfs = data.tfs || ['1m','5m','15m'];
    (data.items || []).forEach(it => {
      const row = document.createElement('div');
      row.className = 'row';
      const sym = document.createElement('div');
      sym.textContent = it.symbol || '—';
      row.appendChild(sym);
      tfs.forEach(tf => {
        const cell = document.createElement('div');
        const s = it.tfs?.[tf]?.status || 'absent';
        const span = document.createElement('span');
        span.className = `dot ${statusToClass(s)}`;
        cell.appendChild(span);
        row.appendChild(cell);
      });
      $rows.appendChild(row);
    });
  }

  async function loadData() {
    try {
      $err.hidden = true;
      const js = await getJSON('/data?ts=' + Date.now());
      render(js);
    } catch (e) {
      console.error('data', e);
      $err.hidden = false;
    }
  }

  // actions
  $btn.addEventListener('click', () => loadData());

  // boot
  await loadVersion();
  await loadData();

  // auto-refresh toutes les 5s (léger)
  setInterval(loadData, 5000);
})();
