from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio

# notre router temps réel
from webviz.realtimeviz.api import router as viz_router, broadcaster, send_test_signal

app = FastAPI(title="SCALP - Realtime Visualization", root_path="")

# CORS permissif (à durcir si besoin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Préfixe /viz pour ne pas mélanger avec d'autres APIs existantes
app.include_router(viz_router, prefix="/viz")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(broadcaster())
    # Un signal d’exemple au démarrage (à retirer en prod si tu veux)
    asyncio.create_task(send_test_signal())

@app.get("/")
def root():
    return {"status": "ok", "service": "scalp-rtviz", "ws": "/viz/ws/stream"}
