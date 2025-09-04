from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from .heatmap import build_dummy_heatmap
from .models import Heatmap
from datetime import datetime, timezone

app = FastAPI(title="SCALP RT-Viz", version="0.1")

@app.get("/test")
def test():
    return {
        "ok": True,
        "ver": "rtviz-0.1",
        "ts": datetime.now(timezone.utc).isoformat()
    }

@app.get("/viz/hello", response_class=PlainTextResponse)
def hello():
    return "hello from rtviz"

@app.get("/viz/heatmap", response_model=Heatmap)
def heatmap():
    return build_dummy_heatmap()
