function showTab(name) {
  ["flux", "heatmap", "hist", "data"].forEach(t => {
    document.getElementById("content-" + t).classList.add("is-hidden");
    document.getElementById("tab-" + t).classList.remove("is-active");
  });
  document.getElementById("content-" + name).classList.remove("is-hidden");
  document.getElementById("tab-" + name).classList.add("is-active");

  if (name === "data") loadDataStatus();
}

async function loadDataStatus() {
  try {
    let res = await fetch("/data_status");
    if (!res.ok) throw new Error("HTTP " + res.status);
    let data = await res.json();

    let tbody = document.getElementById("data-body");
    tbody.innerHTML = "";

    data.forEach(d => {
      let tr = document.createElement("tr");
      let color = "has-text-grey"; // absent par défaut
      if (d.state === "red") color = "has-text-danger";
      if (d.state === "orange") color = "has-text-warning";
      if (d.state === "green") color = "has-text-success";

      tr.innerHTML = `<td>${d.symbol}</td><td>${d.tf}</td><td class="${color}">${d.state}</td>`;
      tbody.appendChild(tr);
    });
  } catch (e) {
    console.error("Erreur loadDataStatus", e);
  }
}
