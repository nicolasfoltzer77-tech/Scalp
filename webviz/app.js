// --- utilitaires DOM déjà présents dans ton app.js ---
// ici on suppose que chaque pastille a un id:  pill-<SYM>-<TF>
// ex: pill-BTC-1m  ; et des classes de couleur: .pill, .fresh, .reloading, .stale, .absent

function setPillState(sym, tf, state){
  const id = `pill-${sym}-${tf}`;
  const el = document.getElementById(id);
  if(!el) return;
  el.classList.remove('fresh','reloading','stale','absent');
  el.classList.add(state);
}

// --- polling existant pour /data (ne pas supprimer) ---
async function refreshDataGrid(){
  try{
    const res = await fetch('/data', {cache: 'no-store'});
    const json = await res.json();
    const symbols = json.symbols || {};
    for(const [sym, states] of Object.entries(symbols)){
      for(const tf of ['1m','5m','15m']){
        const st = (states||{})[tf] || 'absent';
        setPillState(sym, tf, st);
      }
    }
  }catch(e){ /* ignore */ }
}

// rafraîchissement périodique (filet de sécurité)
setInterval(refreshDataGrid, 5000);
refreshDataGrid();

// --- 🔔 Abonnement SSE : bascule instantanée quand 1m devient 'fresh' ---
(function subscribeSSE(){
  try {
    const es = new EventSource('/data/stream');
    es.addEventListener('one_min_fresh', (evt) => {
      const payload = JSON.parse(evt.data); // {sym, tf:'1m', state:'fresh'}
      setPillState(payload.sym, '1m', 'fresh');
    });
    es.onerror = () => {
      // en cas de coupure, le navigateur retente grâce à "retry:" côté serveur
      // on peut aussi fermer/ou relancer ici si besoin
    };
  } catch(e) {
    // si EventSource indisponible, on reste sur le polling
  }
})();
