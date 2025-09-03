import asyncio
from fastapi import FastAPI
from webviz.realtimeviz.api import router, broadcaster, send_test_signal

app = FastAPI()
app.include_router(router)


@app.on_event("startup")
async def startup_event():
    # lancer le broadcaster en tâche de fond
    asyncio.create_task(broadcaster())
    # injecter un exemple au démarrage
    asyncio.create_task(send_test_signal())


@app.get("/")
def root():
    return {"status": "ok", "msg": "RealtimeViz API running"}
