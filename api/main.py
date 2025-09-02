from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import de tes différents modules de routes
from routes import analyse

app = FastAPI(
    title="Scalp API",
    description="API backend du bot Scalp (signaux, positions, heatmap, analyse)",
    version="1.0.0"
)

# Middleware CORS (pour autoriser ton dashboard JS à accéder à l’API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tu pourras restreindre si besoin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routes de base / état ---
@app.get("/api/state")
async def state():
    return {
        "ok": True,
        "mode": "paper",
        "risk_level": 2,
        "balance": 1000.0
    }

@app.get("/api/signals")
async def signals():
    return [
        {
            "ts": 1693651200,
            "sym": "BTCUSDT",
            "side": "buy",
            "score": 78,
            "qty": 150,
            "sl": 24500,
            "tp": [25200, 26000]
        }
    ]

@app.get("/api/positions")
async def positions():
    return [
        {
            "ts": 1693651800,
            "id": "pos_001",
            "sym": "BTCUSDT",
            "side": "long",
            "entry": 24800,
            "qty": 150
        }
    ]

@app.get("/api/heatmap")
async def heatmap():
    return [
        {"sym": "BTCUSDT", "pct": 1.2},
        {"sym": "ETHUSDT", "pct": -0.8},
        {"sym": "SOLUSDT", "pct": 0.5}
    ]

# --- Inclusion des autres routes ---
app.include_router(analyse.router, prefix="/api")
