from fastapi import FastAPI
from fastapi.responses import JSONResponse
import time, random

app = FastAPI()

@app.get("/api/state")
def state():
    return {"ok": True, "mode":"REAL", "balance": 1000, "risk_level": 2}

@app.get("/api/heatmap")
def heatmap():
    # 20 tickers factices 0..100
    syms = ["LINEAUSDT","XPLUSDT","MUSDT","WLFIOUSDT","BASUSDT","BGSCTUSDT",
            "SWEATUSDT","AVAAIUSDT","SOMIUSDT","TAUSDT","FUELUSDT","DOLOUSDT",
            "XNYUSDT","MRTUSDT","ETHUSDT","BTCUSDT","SOLUSDT","ARBUSDT","OPUSDT","TIAUSDT"]
    items = [{"sym": s, "pct": int(random.uniform(10, 90))} for s in syms]
    return {"items": items}

@app.get("/api/signals")
def signals():
    # quelques signaux factices
    now = int(time.time())
    sample = []
    for i in range(3):
        sample.append({
            "ts": now - i*60,
            "sym": random.choice(["LINEAUSDT","XPLUSDT","ETHUSDT","BTCUSDT"]),
            "side": random.choice(["BUY","SELL"]),
            "score": int(random.uniform(60,95)),
            "qty": random.choice([5,10,20]),
            "sl": 0.98,
            "tp": 1.03
        })
    return sample

@app.get("/api/positions")
def positions():
    return []

@app.get("/api/analyse")
def analyse():
    return {
        "best": {"sym":"XPLUSDT","score":92,"buy_above":0.245},
        "reason": "multi-TF momentum + volume",
        "ts": int(time.time())
    }
