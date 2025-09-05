async function loadVersion() {
  try {
    const res = await fetch("/version");
    const data = await res.json();
    document.getElementById("ver").textContent = `rtviz-ui ${data.ui}`;
  } catch {
    document.getElementById("ver").textContent = "rtviz-ui ?";
  }
}

// 🔄 Bouton de mise à jour (force reload avec cache-buster)
document.addEventListener("DOMContentLoaded", () => {
  loadVersion();

  const btn = document.getElementById("btn-update");
  if (btn) {
    btn.addEventListener("click", () => {
      const ts = Date.now();
      location.href = `/?v=${ts}`;
    });
  }
});
