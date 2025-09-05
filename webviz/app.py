from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI()

# 👉 Dossier où se trouvent index.html, app.js, style.css
FRONT_DIR = "/opt/scalp/webviz"

# Servir les fichiers statiques (JS, CSS…)
app.mount("/static", StaticFiles(directory=FRONT_DIR), name="static")

@app.get("/")
async def root():
    """Renvoie l'index du dashboard"""
    return FileResponse(os.path.join(FRONT_DIR, "index.html"))

# Exemple d’API pour l’onglet Data
@app.get("/api/data_status")
async def data_status():
    """
    Retourne l’état des fichiers CSV dans /opt/scalp/data/klines
    - gris  : absent
    - rouge : trop vieux
    - orange: en cours de rechargement
    - vert  : ok
    """
    import glob, time
    DATA_DIR = "/opt/scalp/data/klines"
    now = time.time()
    status = {}

    for f in glob.glob(os.path.join(DATA_DIR, "*.csv")):
        name = os.path.basename(f).replace(".csv", "")
        age = now - os.path.getmtime(f)

        if age > 3600:   # trop vieux > 1h
            state = "rouge"
        elif age > 600:  # vieux > 10min
            state = "orange"
        else:
            state = "vert"

        status[name] = {"file": f, "age_sec": int(age), "state": state}

    return status
