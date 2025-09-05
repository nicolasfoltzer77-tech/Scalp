from __future__ import annotations
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Import des routeurs existants
from routes.logs import router as logs_router
from routes.streams import router as streams_router
from routes.diag import router as diag_router
from routes.data import router as data_router   # ✅ nouvel onglet Data

app = FastAPI(title="SCALP Webviz")

# CORS si besoin (API accessible depuis ton frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montage des fichiers statiques (frontend Vue/JS/HTML)
www_dir = os.path.join(os.path.dirname(__file__), "../www")
app.mount("/", StaticFiles(directory=www_dir, html=True), name="static")

# Brancher les routeurs
app.include_router(logs_router)
app.include_router(streams_router)
app.include_router(diag_router)
app.include_router(data_router)   # ✅ nouveau
