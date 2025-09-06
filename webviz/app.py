from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse
from pathlib import Path
import json

app = FastAPI()

@app.get("/version")
def version():
    vf = Path("/opt/scalp/webviz/VERSION")
    ui = vf.read_text().strip() if vf.exists() else "0.0.0"
    return {"ui": ui}

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/data")
def data():
    p = Path("/opt/scalp/runtime/data.json")
    if not p.exists():
        return JSONResponse({"detail":"Not Found"}, status_code=503)
    try:
        return JSONResponse(json.loads(p.read_text()))
    except Exception as e:
        return JSONResponse({"detail": f"Invalid JSON: {e}"}, status_code=500)

# ---- NEW: derniers .json dans /opt/scalp/data
@app.get("/logs/last10data")
def last10data():
    p = Path("/opt/scalp/data/last10-data.json")
    if not p.exists():
        return JSONResponse([])
    try:
        return JSONResponse(json.loads(p.read_text()))
    except Exception as e:
        return JSONResponse({"detail": f"Invalid JSON: {e}"}, status_code=500)
