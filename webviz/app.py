from fastapi import FastAPI, Response, status
from fastapi.responses import JSONResponse, PlainTextResponse, FileResponse
from starlette.staticfiles import StaticFiles
from pathlib import Path
import json, time, logging, os

# ---------- LOGGING VERBEUX ----------
LOG_LEVEL = os.getenv("WEBVIZ_LOG", "DEBUG").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
log = logging.getLogger("webviz")

ROOT = Path("/opt/scalp/webviz")
ASSETS = ROOT / "assets"
INDEX = ROOT / "index.html"
APPJS = ROOT / "app.js"
VERSION_FILE = ROOT / "VERSION"

# Emplacement d’un dump JSON produit par le loader (fallback si API interne absente)
DATA_JSON = Path(os.getenv("SCALP_DATA_JSON", "/opt/scalp/runtime/data.json"))

UI_VER = (VERSION_FILE.read_text().strip() if VERSION_FILE.exists() else "0.0.0")

app = FastAPI(title="SCALP rtviz-ui", docs_url=None, redoc_url=None, openapi_url=None)

# ---------- STATIC ----------
app.mount("/assets", StaticFiles(directory=str(ASSETS), html=False), name="assets")

# ---------- ENDPOINTS ----------
@app.get("/healthz")
def healthz():
    log.debug("GET /healthz")
    return {"ok": True, "ui": UI_VER}

@app.get("/version")
def version():
    log.debug("GET /version -> %s", UI_VER)
    return {"ui": UI_VER}

@app.get("/", response_class=FileResponse)
def root():
    log.debug("GET / -> index.html")
    return FileResponse(str(INDEX))

@app.get("/app.js")
def get_app_js():
    log.debug("GET /app.js (no-cache)")
    return Response(APPJS.read_text(), media_type="application/javascript", headers={
        "Cache-Control": "no-store"
    })

# ---------- /data : toujours présent ----------
@app.get("/data")
def data():
    """
    1) Si un fichier runtime existe: on le renvoie (chemin SCALP_DATA_JSON)
    2) Sinon -> 503 avec explication + log
    (Ça évite les 404 qui cassaient l'UI)
    """
    log.debug("GET /data")
    if DATA_JSON.exists():
        try:
            raw = DATA_JSON.read_text()
            # Log taille + timestamp pour debug
            log.info("Serving /data from %s (%d bytes)", DATA_JSON, len(raw))
            # Valider JSON grossièrement
            j = json.loads(raw)
            # ajout d'un champ ui pour traçabilité
            j.setdefault("ui", UI_VER)
            return JSONResponse(j, headers={"Cache-Control": "no-store"})
        except Exception as e:
            log.exception("Error reading %s: %s", DATA_JSON, e)
            return JSONResponse(
                {"error": "bad_data", "detail": str(e), "ui": UI_VER},
                status_code=status.HTTP_502_BAD_GATEWAY,
            )
    else:
        log.error("DATA source not found: %s", DATA_JSON)
        return JSONResponse(
            {
                "error": "no_data",
                "detail": f"DATA_JSON not found: {DATA_JSON}",
                "hint": "vérifie le loader ou configure SCALP_DATA_JSON",
                "ui": UI_VER,
            },
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
