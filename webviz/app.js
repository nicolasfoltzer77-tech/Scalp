/* rtviz-ui app.js – robuste contre les 404 (multi-endpoints) */

/* ===== helpers ===== */
async function tryFetchJSON(urls) {
  const errs = [];
  for (const u of urls) {
    try {
      const r = await fetch(u, {cache: "no-store"});
      if (r.ok) return await r.json();
      errs.push(`${u} -> ${r.status}`);
    } catch (e) {
      errs.push(`${u} -> ${e}`);
    }
  }
  throw new Error(errs.join(" | "));
}
function td(txt, cls="") {
  const d = document.createElement("td");
  d.textContent = txt ?? "";
  if (cls) d.className = cls;
  return d;
}
function tr(cells=[]) {
  const r = document.createElement("tr");
  cells.forEach(c => r.appendChild(c));
  return r;
}
function fmtTs(ts) {
  const n = Number(ts);
  if (!Number.isFinite(n)) return String(ts);
  const d = new Date(n*1000);
  return d.toLocaleString();
}

/* ===== endpoints (avec fallbacks) ===== */
const ENDPOINTS = {
  signals:   ["/signals", "/api/signals", "/viz/signals"],
  heatmap:   ["/heatmap", "/viz/heatmap", "/api/heatmap"],
  history:   (sym) => [`/history/${sym}`, `/api/history/${sym}`, `/viz/history/${sym}`],
  data:      ["/api/data_status", "/viz/data_status", "/data_status"]
};

/* ====== Onglet FLUX ====== */
async function loadFlux() {
  const tbody = document.getElementById("flux-body");
  const errBox = document.getElementById("flux-error");
  tbody.innerHTML = ""; errBox.textContent = "";

  try {
    const items = await tryFetchJSON(ENDPOINTS.signals);
    // items = [{ts,sym,tf,side,score,entry,rsi,sma,ema}] – champs optionnels tolérés
    items.forEach(it => {
      const side = (it.side || it.signal || "HOLD").toUpperCase();
      const cls = side === "BUY" ? "green" : side === "SELL" ? "red" : "";
      const rsi = it.rsi ?? "";
      const sma = it.sma ?? "";
      const ema = it.ema ?? "";
      const score = it.score ?? "";
      const entry = it.entry ?? "";

      tbody.appendChild(tr([
        td(fmtTs(it.ts)),
        td(it.sym || it.symbol || ""),
        td(it.tf || ""),
        td(side, cls),
        td(rsi),
        td(sma),
        td(ema),
        td(score)
      ]));
    });
  } catch (e) {
    errBox.textContent = "Erreur de chargement flux: " + e.message;
  }
}

/* ====== Onglet HEATMAP ====== */
async function loadHeatmap() {
  const box = document.getElementById("heatmap-body");
  const err = document.getElementById("heatmap-error");
  box.textContent = ""; err.textContent = "";
  try {
    const data = await tryFetchJSON(ENDPOINTS.heatmap);
    box.textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    err.textContent = "Erreur de chargement heatmap: " + e.message;
  }
}

/* ====== Onglet HISTORIQUE ====== */
async function loadHistory(sym="BTCUSDT") {
  const tbody = document.getElementById("history-body");
  const err = document.getElementById("history-error");
  tbody.innerHTML = ""; err.textContent = "";
  try {
    const data = await tryFetchJSON(ENDPOINTS.history(sym));
    // data: {items:[{ts,tf,side,score,rsi,sma,ema}]} OU directement un tableau
    const items = Array.isArray(data) ? data : (data.items || []);
    items.forEach(it => {
      const side = (it.side || it.signal || "HOLD").toUpperCase();
      const cls = side === "BUY" ? "green" : side === "SELL" ? "red" : "";
      tbody.appendChild(tr([
        td(fmtTs(it.ts)),
        td(it.tf || ""),
        td(side, cls),
        td(it.rsi ?? ""),
        td(it.sma ?? ""),
        td(it.ema ?? ""),
        td(it.score ?? "")
      ]));
    });
  } catch (e) {
    err.textContent = "Erreur de chargement historique: " + e.message;
  }
}

/* ====== Onglet DONNÉES ======
   data_status renvoie par ex:
   { "LINK": { "1m": {"state":"fresh"}, "5m":{"state":"stale"}, "15m":{"state":"loading"} }, ... }
   États mappés → couleurs:
     fresh -> green, loading -> orange, stale -> red, missing -> grey
*/
function stateClass(s) {
  const m = (s||"").toLowerCase();
  if (m === "fresh")   return "green";
  if (m === "loading") return "orange";
  if (m === "stale")   return "red";
  return "grey";
}
async function loadData() {
  const tbody = document.getElementById("data-body");
  const err = document.getElementById("data-error");
  tbody.innerHTML = ""; err.textContent = "";

  try {
    const data = await tryFetchJSON(ENDPOINTS.data);
    // tri alpha sur symbole
    const symbols = Object.keys(data||{}).sort();
    symbols.forEach(sym => {
      const s = data[sym] || {};
      const c1 = s["1m"]?.state || s["1m"] || "missing";
      const c5 = s["5m"]?.state || s["5m"] || "missing";
      const c15 = s["15m"]?.state || s["15m"] || "missing";
      tbody.appendChild(tr([
        td(sym),
        td(typeof c1==="string"?c1:JSON.stringify(c1), stateClass(c1)),
        td(typeof c5==="string"?c5:JSON.stringify(c5), stateClass(c5)),
        td(typeof c15==="string"?c15:JSON.stringify(c15), stateClass(c15)),
      ]));
    });
  } catch (e) {
    err.textContent = "Erreur de chargement des données: " + e.message;
  }
}

/* ===== chargement initial & rafraîchissement léger ===== */
function init() {
  // charge tous les onglets une fois
  loadFlux();
  loadHeatmap();
  loadHistory("BTCUSDT");
  loadData();

  // rafraîchis le flux et l’état data toutes les 10s sans surcharger
  setInterval(loadFlux, 10000);
  setInterval(loadData, 15000);
}
document.addEventListener("DOMContentLoaded", init);
