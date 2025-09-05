from __future__ import annotations
import os, json, time
from fastapi import FastAPI, Response
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

APP_DIR = "/opt/scalp/webviz"
DASH_DIR = "/opt/scalp/var/dashboard"
DATA_STATUS = os.path.join(DASH_DIR, "data_status.json")   # généré par ton job côté data

app = FastAPI()

# CORS + anti-cache côté API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

def _nocache(resp: Response) -> Response:
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

# --------- Pages (index + js) ---------
@app.get("/", include_in_schema=False)
def root():
    path = os.path.join(APP_DIR, "index.html")
    return _nocache(FileResponse(path, media_type="text/html"))

@app.get("/app.js", include_in_schema=False)
def appjs():
    path = os.path.join(APP_DIR, "app.js")
    return _nocache(FileResponse(path, media_type="text/javascript"))

# --------- API utilitaires ---------
@app.get("/hello", include_in_schema=False)
def hello():
    return PlainTextResponse("hello from rtviz")

@app.get("/version")
def version():
    return _nocache(JSONResponse({"ui":"1.0.2", "ts": int(time.time())}))

# --------- API historiques existants (inchangés) ---------
# /signals et /heatmap sont déjà implémentés ailleurs dans ton app ;
# on ne modifie pas leur logique ici.

# --------- NOUVEAU : API Data (onglet Données) ---------
@app.get("/data")
def data_status():
    """
    Sert tel quel le fichier JSON préparé par ton job:
    {
      "updated_at": 17570...,      # epoch
      "tfs": ["1m","5m","15m","1h",...],
      "items": [
        {"symbol":"BTC", "tfs":{
           "1m":{"status":"fresh","age_sec":12},
           "5m":{"status":"stale","age_sec":620},
           "15m":{"status":"reloading","age_sec":90},
           "1h":{"status":"absent","age_sec":null}
        }},
        ...
      ]
    }
    """
    try:
        if os.path.isfile(DATA_STATUS):
            with open(DATA_STATUS, "r", encoding="utf-8") as f:
                payload = json.load(f)
        else:
            payload = {"updated_at": int(time.time()), "tfs": [], "items": []}
        return _nocache(JSONResponse(payload))
    except Exception as e:
        return _nocache(JSONResponse({"error": str(e), "items": []}))
