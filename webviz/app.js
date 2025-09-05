// /opt/scalp/webviz/app.js

// --- Helpers ---
const $ = (sel, ctx=document) => ctx.querySelector(sel);
const $$ = (sel, ctx=document) => Array.from(ctx.querySelectorAll(sel));
const TF_LIST = ["1m","5m","15m"];           // tfs affichés
const COLOR_MAP = { gris:"#7f8c8d", rouge:"#e74c3c", orange:"#f39c12", vert:"#27ae60" };

function pill(state, txt=state) {
  const color = COLOR_MAP[state] || "#7f8c8d";
  return `<span style="
    display:inline-block;padding:.2rem .5rem;border-radius:.6rem;
    color:#111;background:${color};font-weight:600;min-width:3.2rem;
    text-align:center;color:#fff">${txt}</span>`;
}

function setActive(tabId) {
  $$(".tabs .tab").forEach(el => el.classList.remove("active"));
  $(`#${tabId}`)?.classList.add("active");
  $$(".view").forEach(v => v.classList.add("hidden"));
  $(`#view-${tabId.replace("tab-","")}`)?.classList.remove("hidden");
}

// --- Onglet DATA ---
async function loadDataStatus() {
  const res = await fetch("/api/data_status", { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json(); // { "BTCUSDT_1m": {file, age_sec, state}, ... }
}

/**
 * Transforme le JSON {SYMBTF: {...}} => Map {sym => {tf => state}}
 * - supprime le suffixe USDT dans le symbole pour l’affichage
 * - marque "gris" pour les tf manquants
 */
function normalizeStatus(raw) {
  const table = new Map(); // sym -> { tf -> {state, age} }
  for (const [key, obj] of Object.entries(raw)) {
    // key ex: "BTCUSDT_1m"
    const m = key.match(/^([A-Z0-9]+)_(\d+m|[1-9]\dh)$/i);
    if (!m) continue;
    let sym = m[1].replace(/USDT$/i, "");  // afficher sans USDT
    const tf = m[2];

    if (!table.has(sym)) table.set(sym, {});
    table.get(sym)[tf] = { state: obj.state || "gris", age: obj.age_sec ?? null };
  }

  // injecte "gris" si des TF manquent
  for (const [sym, tfs] of table.entries()) {
    TF_LIST.forEach(tf => {
      if (!tfs[tf]) tfs[tf] = { state: "gris", age: null };
    });
  }
  return table;
}

function fmtAge(sec) {
  if (sec == null) return "—";
  if (sec < 90) return `${sec}s`;
  const m = Math.floor(sec/60);
  if (m < 90) return `${m}m`;
  const h = Math.floor(m/60);
  return `${h}h`;
}

function renderDataTable(table) {
  const rows = [];
  rows.push(`
    <div style="margin:.5rem 0 1rem 0">
      Légende : ${pill("vert","ok")} ${pill("orange","reload")}
      ${pill("rouge","vieux")} ${pill("gris","absent")}
    </div>
  `);
  rows.push(`
    <table class="datatable" style="width:100%;border-collapse:separate;border-spacing:0 .4rem">
      <thead>
        <tr>
          <th style="text-align:left;padding:.6rem 1rem">sym</th>
          ${TF_LIST.map(tf => `<th style="text-align:center;padding:.6rem 1rem">${tf}</th>`).join("")}
        </tr>
      </thead>
      <tbody>
        ${[...table.entries()].sort((a,b)=>a[0].localeCompare(b[0])).map(([sym, tfs]) => {
          return `
            <tr>
              <td style="padding:.5rem 1rem;font-weight:700;opacity:.9">${sym}</td>
              ${TF_LIST.map(tf => {
                const cell = tfs[tf] || {state:"gris", age:null};
                return `<td style="text-align:center;padding:.5rem 1rem">${pill(cell.state, fmtAge(cell.age))}</td>`;
              }).join("")}
            </tr>
          `;
        }).join("")}
      </tbody>
    </table>
  `);
  $("#data-container").innerHTML = rows.join("");
}

async function showDataTab() {
  setActive("tab-data");
  $("#data-container").innerHTML = `<div style="opacity:.7">Chargement…</div>`;
  try {
    const raw = await loadDataStatus();
    const table = normalizeStatus(raw);
    renderDataTable(table);
  } catch (e) {
    $("#data-container").innerHTML = `<div style="color:#e74c3c">Erreur: ${e.message}</div>`;
  }
}

// --- Onglets existants (si présents dans ton index.html) ---
async function showFluxTab(){ setActive("tab-flux"); /* ... garder ton code existant si nécessaire ... */ }
async function showHeatmapTab(){ setActive("tab-heatmap"); /* ... */ }
async function showHistoriqueTab(){ setActive("tab-historique"); /* ... */ }

// --- Boot ---
document.addEventListener("DOMContentLoaded", () => {
  // boutons d’onglets s’ils existent
  $("#tab-flux")?.addEventListener("click", showFluxTab);
  $("#tab-heatmap")?.addEventListener("click", showHeatmapTab);
  $("#tab-historique")?.addEventListener("click", showHistoriqueTab);
  $("#tab-data")?.addEventListener("click", showDataTab);

  // onglet par défaut : Data si présent, sinon Heatmap
  if ($("#tab-data")) showDataTab();
  else if ($("#tab-heatmap")) showHeatmapTab();
});
