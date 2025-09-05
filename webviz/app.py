import time
from fastapi import FastAPI
from fastapi.responses import FileResponse
import os

app = FastAPI()

# Version unique centralisée
__version__ = "1.0.4"

# 📂 Chemin du dossier web
WEB_DIR = "/opt/scalp/webviz"

@app.get("/version")
async def version():
    return {"ui": __version__, "ts": int(time.time())}

@app.get("/")
async def index():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))

@app.get("/app.js")
async def appjs():
    return FileResponse(os.path.join(WEB_DIR, "app.js"))
