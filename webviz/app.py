from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import json, time

ROOT = Path("/opt/scalp/webviz").resolve()
app  = FastAPI()

# ---------- Version ----------
def read_version() -> str:
    p = ROOT / "VERSION"
    try:
        return p.read_text().strip()
    except Exception:
        return "0.0.0"

@app.get("/version")
def version():
    return {"ui": read_version(), "ts": int(time.time())}

# ---------- Pages & statics ----------
# Sert /app.js et /assets/* avec les bons MIME
app.mount("/assets", StaticFiles(directory=str(ROOT / "assets")), name="assets")
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")

@app.get("/app.js")
def app_js():
    p = ROOT / "app.js"
    return Response(p.read_text(), media_type="application/javascript; charset=utf-8")

@app.get("/", response_class=HTMLResponse)
def index():
    # renvoie du HTML, pas un txt/attachment
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html, status_code=200)

# ---------- API métiers (déjà existantes) ----------
# /signals, /heatmap, /data doivent exister côté service.
# Je garde des stubs défensifs si jamais un import saute.
DATA_FILE = ROOT / "data.json"  # facultatif

@app.get("/data")
def data():
    if DATA_FILE.exists():
        try:
            return JSONResponse(json.loads(DATA_FILE.read_text()))
        except Exception:
            pass
    return JSONResponse({"detail": "Not Found"}, status_code=404)
