async function loadVersion() {
  try {
    const r = await fetch('/version');
    const js = await r.json();
    document.getElementById('ver').innerText = `rtviz-ui ${js.ui}`;
  } catch (e) {
    document.getElementById('ver').innerText = "rtviz-ui ?";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadVersion();
  // on pourra relancer aussi sur clic du bouton update si besoin
  document.getElementById("btn-update").addEventListener("click", loadVersion);
});
