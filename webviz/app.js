(async function () {
  const $ = s => document.querySelector(s);
  const $$ = s => Array.from(document.querySelectorAll(s));

  // --- version UI ---
  async function loadVersion() {
    try {
      const r = await fetch("/version", {cache:"no-store"});
      const js = await r.json();
      $("#ver").textContent = `rtviz-ui ${js.ui}`;
    } catch {
      $("#ver").textContent = "rtviz-ui ?";
    }
  }

  // --- onglets ---
  function bindTabs() {
    $$("#tabs .tab").forEach(btn=>{
      btn.addEventListener("click", ()=>{
        $$("#tabs .tab").forEach(b=>b.classList.remove("active"));
        btn.classList.add("active");
        const name = btn.dataset.tab;
        ["flux","heatmap","history","data"].forEach(t=>{
          $("#tab-"+t).style.display = (t===name)?"block":"none";
        });
        if (name==="data") renderData();   // lazy load
        if (name==="flux") renderFlux();
        if (name==="heatmap") renderHeatmap();
      })
    });
  }

  // --- bouton MAJ (force reload dur) ---
  $("#btn-update").addEventListener("click", ()=>{
    // Ajoute un cache-buster à l’URL courante
    const u = new URL(window.location.href);
    u.searchParams.set("v", Date.now().toString().slice(-6));
    location.href = u.toString();
  });

  // -------- Flux (placeholder simple) --------
  async function renderFlux() {
    const err = $("#flux-error"); err.style.display="none";
    const body = $("#flux-table tbody"); body.innerHTML = "";
    try {
      const r = await fetch("/signals", {cache:"no-store"});
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      const rows = await r.json();
      (rows||[]).slice(0,50).forEach(o=>{
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${o.ts||""}</td><td>${o.sym||o.symbol||""}</td><td>${o.tf||""}</td>
                        <td>${o.side||o.signal||""}</td><td>${o.score??""}</td><td>${o.entry??""}</td>`;
        body.appendChild(tr);
      });
    } catch(e) {
      err.textContent = "Erreur de chargement."; err.style.display="block";
    }
  }

  // -------- Heatmap (placeholder) --------
  async function renderHeatmap() {
    const err = $("#heatmap-error"); err.style.display="none";
    const root = $("#heatmap-grid"); root.innerHTML = "";
    try {
      const r = await fetch("/heatmap", {cache:"no-store"});
      if (!r.ok) throw new Error();
      const js = await r.json();
      root.textContent = JSON.stringify(js).slice(0,400)+"…"; // minimal, on ne casse rien
    } catch {
      err.textContent = "Erreur de chargement heatmap."; err.style.display="block";
    }
  }

  // -------- Données (nouvel onglet) --------
  function statClass(s) {
    if (!s || s==="absent" || s==="unknown") return "st-grey";
    if (s==="stale" || s==="invalid") return "st-red";
    if (s==="reloading" || s==="loading") return "st-orange";
    return "st-green"; // fresh / ok
  }

  async function renderData() {
    const err = $("#data-error"); err.style.display = "none";
    $("#data-head").innerHTML = ""; $("#data-body").innerHTML = ""; $("#data-meta").textContent="";
    try {
      const r = await fetch("/data", {cache:"no-store"});
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      const js = await r.json();

      const tfs = js.tfs || []; // ex: ["1m","5m","15m","1h"]
      // entête
      const trh = document.createElement("tr");
      trh.innerHTML = `<th>Symbol</th>` + tfs.map(tf=>`<th>${tf}</th>`).join("");
      $("#data-head").appendChild(trh);

      // lignes
      (js.items||[]).forEach(row=>{
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${(row.symbol||"").replace(/USDT$/,"")}</td>` +
           tfs.map(tf=>{
             const info = (row.tfs||{})[tf] || {};
             const st = info.status || "absent";
             const age = (info.age_sec!=null)? `${info.age_sec}s` : "";
             return `<td><span class="pill ${statClass(st)}">${st}${age?` · ${age}`:""}</span></td>`;
           }).join("");
        $("#data-body").appendChild(tr);
      });

      if (js.updated_at) {
        const dt = new Date(js.updated_at*1000);
        $("#data-meta").textContent = `Mise à jour: ${dt.toLocaleString()}`;
      }
    } catch(e) {
      err.textContent = "Erreur de chargement des données."; err.style.display="block";
    }
  }

  // init
  await loadVersion();
  bindTabs();
  renderFlux(); // onglet par défaut
})();
