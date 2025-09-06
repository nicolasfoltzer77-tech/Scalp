from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.staticfiles import StaticFiles
from pathlib import Path
import os

ROOT_CORE = Path("/opt/scalp/ui-core")
ROOT_MODS = Path("/opt/scalp/ui-mods")
SHARED = Path("/opt/scalp/ui-shared")
VERSION_FILE = SHARED / "VERSION"

app = FastAPI()

# --- Health/ready (pour Caddy, monitoring)
@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/ready")
def ready():
    # on considère ready si index core existe
    return {"ready": (ROOT_CORE / "index.html").exists()}

# --- Version UI
@app.get("/version")
def version():
    v = "0.0.0"
    try:
        v = VERSION_FILE.read_text().strip()
    except FileNotFoundError:
        pass
    return {"ui": v}

# --- Fichiers statiques dédiés (ex: /assets/... si besoin)
app.mount("/mods", StaticFiles(directory=str(ROOT_MODS), html=False), name="mods")
app.mount("/core", StaticFiles(directory=str(ROOT_CORE), html=False), name="core")

def _pick(path: str) -> Path | None:
    p_mods = ROOT_MODS / path
    if p_mods.is_file():
        return p_mods
    p_core = ROOT_CORE / path
    if p_core.is_file():
        return p_core
    return None

# Fallback “try mods then core” pour tout le reste
@app.get("/{full_path:path}")
def any_file(full_path: str):
    # page d’accueil
    if full_path in ("", "/"):
        full_path = "index.html"
    p = _pick(full_path)
    if p:
        # Types mimes corrects via FileResponse
        return FileResponse(str(p))
    return JSONResponse({"detail": "Not Found"}, status_code=404)
