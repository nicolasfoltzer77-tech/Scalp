from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os

ROOT = "/opt/scalp/webviz"
VERSION_FILE = os.path.join(ROOT, "VERSION")

app = FastAPI()

# Routes API version
@app.get("/version")
async def version():
    try:
        with open(VERSION_FILE, "r") as f:
            v = f.read().strip()
    except FileNotFoundError:
        v = "0.0.0"
    return {"ui": v}

# Route pour la page principale
@app.get("/")
async def root():
    return FileResponse(os.path.join(ROOT, "index.html"))

# Fichiers statiques (js, css…)
app.mount("/", StaticFiles(directory=ROOT), name="static")
