async function loadVersion() {
  try {
    const res = await fetch('/version');
    const v = await res.json();
    document.getElementById('version').innerText = `rtviz-ui ${v.ui}`;
  } catch (e) {
    document.getElementById('version').innerText = "version inconnue";
  }
}

async function loadData() {
  try {
    const res = await fetch('/data');
    if (!res.ok) throw new Error("Erreur API");
    const data = await res.json();
    document.getElementById('data').innerText = JSON.stringify(data, null, 2);
  } catch (e) {
    document.getElementById('data').innerText = "Impossible de charger les données.";
  }
}

window.onload = () => {
  loadVersion();
  loadData();
};
