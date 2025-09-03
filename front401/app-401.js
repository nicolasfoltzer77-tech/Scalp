// /* front-version: 4.0-min */
console.log('Scalp front 4.0-min');
(async () => {
  try {
    const s = await fetch('/api/state', {cache:'no-store'}).then(r=>r.json());
    const ver = (s && s.version) ? s.version : '?.?';

    // Bandeau visible pour vérifier qu'on charge bien CE fichier
    const b = document.createElement('div');
    b.textContent = `front ${ver} (API ${ver})`;
    b.style = 'position:fixed;top:8px;left:8px;z-index:99999;background:#22c55e;color:#0b0f17;padding:6px 10px;border-radius:6px;font:600 12px system-ui';
    document.addEventListener('DOMContentLoaded',()=>document.body.prepend(b));

    // Remplace le badge "v 3.xx" dans la page s’il existe
    const el = [...document.querySelectorAll('*')].find(x => /^\s*v\s*\d/.test(x.textContent||''));
    if (el) el.textContent = 'v ' + ver;
  } catch(e) { console.error('version fetch failed', e); }
})();
