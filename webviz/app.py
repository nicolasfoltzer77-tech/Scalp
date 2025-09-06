# /opt/scalp/webviz/app.py
import os, json, time, logging
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from starlette.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s webviz :: %(message)s")
log = logging.getLogger("webviz")

ROOT = Path("/opt/scalp/webviz")
VERSION_FILE = Path(os.getenv("SCALP_VERSION_FILE", ROOT / "VERSION"))
DATA_FILE = Path(os.getenv("SCALP_DATA_JSON", "/opt/scalp/runtime/data.json"))

def ui_version() -> str:
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    except Exception as e:
        log.error("VERSION read error: %s", e)
        return "0.0.0"

def load_data():
    if not DATA_FILE.exists():
        log.error("DATA source not found: %s", DATA_FILE)
        raise FileNotFoundError(f"{DATA_FILE}")
    with DATA_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)

app = FastAPI()

# Static (optionnel)
assets = ROOT / "assets"
if assets.exists():
    app.mount("/assets", StaticFiles(directory=str(assets), html=False), name="assets")

@app.get("/healthz")
def healthz():
    return {"ok": True, "ui": ui_version(), "ts": int(time.time())}

@app.get("/version")
def version():
    return {"ui": ui_version()}

@app.get("/data")
def data():
    try:
        return load_data()
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="data.json missing")
    except Exception as e:
        log.exception("DATA load failure")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def root():
    return HTMLResponse(f"""
<!doctype html><meta charset="utf-8">
<title>SCALP rtviz-ui {ui_version()}</title>
<div style="padding:16px;color:#e6edf3;background:#0f141a;font-family:system-ui,Segoe UI,Roboto,Arial">
  <h1>SCALP rtviz-ui {ui_version()}</h1>
  <p><a href="/version">/version</a> · <a href="/healthz">/healthz</a> · <a href="/data">/data</a></p>
  <p>Si /data renvoie 503, crée ou renseigne /opt/scalp/runtime/data.json</p>
</div>
""")
