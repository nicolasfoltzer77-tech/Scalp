from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def dashboard():
    html = """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <title>SCALP Dashboard</title>
        <style>
            body { background:#111; color:#eee; font-family:sans-serif; }
            h1 { color:#0f0; }
            .heatmap { display:flex; flex-wrap:wrap; gap:10px; }
            .cell { padding:10px; border-radius:6px; color:#fff; font-weight:bold; }
            #wslog { background:#000; color:#0f0; padding:10px; height:200px; overflow:auto; }
        </style>
    </head>
    <body>
        <h1>🔥 SCALP Dashboard</h1>

        <h2>Heatmap</h2>
        <div id="heatmap" class="heatmap">Chargement...</div>

        <h2>WebSocket Live</h2>
        <div id="wslog">Connecting...</div>

        <script>
        async function loadHeatmap() {
            try {
                const res = await fetch("/heatmap");
                if (!res.ok) return;
                const data = await res.json();
                const box = document.getElementById("heatmap");
                box.innerHTML = "";
                data.cells.forEach(c => {
                    const div = document.createElement("div");
                    div.className = "cell";
                    const score = c.score;
                    const color = score > 0 ? "green" : "magenta";
                    div.style.background = color;
                    div.innerText = c.symbol + " " + score;
                    box.appendChild(div);
                });
            } catch(e) {
                console.error("heatmap error", e);
            }
        }
        loadHeatmap();
        setInterval(loadHeatmap, 5000);

        // WebSocket
        const ws = new WebSocket("ws://" + window.location.host + "/viz/ws/stream");
        const wslog = document.getElementById("wslog");
        ws.onmessage = (ev) => {
            wslog.innerText += "\\n" + ev.data;
            wslog.scrollTop = wslog.scrollHeight;
        };
        ws.onopen = () => wslog.innerText = "Connected to WS...";
        ws.onerror = () => wslog.innerText += "\\nWS error!";
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)
