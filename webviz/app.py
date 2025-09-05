from fastapi import FastAPI
from fastapi.responses import JSONResponse
import time

app = FastAPI()

# Version courante de l'UI
UI_VERSION = "1.0.4"
START_TS = int(time.time())

@app.get("/version")
def version():
    return {"ui": UI_VERSION, "ts": START_TS}

# Endpoint de ping
@app.get("/hello")
def hello():
    return {"msg": "hello from scalp-rtviz"}

# Endpoint logs (placeholder)
@app.get("/logs/")
def logs():
    return {"logs": ["log1", "log2", "log3"]}

# Endpoint data → pour les pastilles
@app.get("/data")
def data():
    return {
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
