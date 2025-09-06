from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import json
import time

# --- Versioning ---
VERSION_FILE = Path(__file__).parent / "VERSION"
if VERSION_FILE.exists():
    UI_VERSION = VERSION_FILE.read_text().strip()
else:
    UI_VERSION = "0.0.0"

# --- Init FastAPI ---
app = FastAPI(title="SCALP RTViz")

# --- Assets directory ---
ROOT = Path(__file__).parent
assets_dir = ROOT / "assets"
assets_dir.mkdir(parents=True, exist_ok=True)

app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

# --- API endpoints ---

@app.get("/version")
async def version():
    return {"ui": UI_VERSION, "ts": int(time.time())}

@app.get("/hello")
async def hello():
    return JSONResponse(content={"msg": "Hello from SCALP RTViz!"})

@app.get("/data")
async def data():
    # ⚠️ Ici, tu devras connecter avec ton vrai backend/data loader
    # Pour l’instant on simule une réponse minimale
    sample = {
        "tfs": ["1m", "5m", "15m"],
        "min_candles": 1500,
        "items": [
            {
                "symbol": "BTC",
                "tfs": {
                    "1m": {"status": "fresh", "candles": 1500},
                    "5m": {"status": "reloading", "candles": 800},
                    "15m": {"status": "stale", "candles": 200},
                },
            },
            {
                "symbol": "ETH",
                "tfs": {
                    "1m": {"status": "fresh", "candles": 1500},
                    "5m": {"status": "fresh", "candles": 1500},
                    "15m": {"status": "absent", "candles": 0},
                },
            },
        ],
        "updated_at": int(time.time()),
    }
    return JSONResponse(content=sample)
