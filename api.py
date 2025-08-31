#!/usr/bin/env python3
import os, json, time
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import ccxt

DOCS = "/opt/scalp/docs"
F_SIGNALS = f"{DOCS}/signals.json"
F_POSITIONS = f"{DOCS}/positions.json"
F_BALANCE = f"{DOCS}/bitget_balance.json"
F_RISK = f"{DOCS}/risk_level.json"

API_KEY = os.getenv("API_KEY", "")           # clé simple pour POST
DRY_RUN = int(os.getenv("DRY_RUN", "0") or "0")
BITGET_ACCESS_KEY = os.getenv("BITGET_ACCESS_KEY","")
BITGET_SECRET_KEY = os.getenv("BITGET_SECRET_KEY","")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE","")
LIVE_MARKET = os.getenv("LIVE_MARKET","umcbl")  # futures USDT
exchange = None

def get_exchange():
    global exchange
    if exchange is None:
        exchange = ccxt.bitget({
            "apiKey": BITGET_ACCESS_KEY,
            "secret": BITGET_SECRET_KEY,
            "password": BITGET_PASSPHRASE,
            "options": {"defaultType": "swap"}, # futures
            "enableRateLimit": True,
        })
    return exchange

def read_json(path, default):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default

def write_json(path, data):
    tmp = f"{path}.tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, separators=(",", ":"), ensure_ascii=False)
    os.replace(tmp, path)

app = FastAPI(title="SCALP API", version="1.0")

class RiskBody(BaseModel):
    level: int

class CloseBody(BaseModel):
    symbol: str
    side: str | None = None  # "long" ou "short" si utile

def check_api_key(x_api_key: str | None):
    if not API_KEY:
        return
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Bad API key")

@app.get("/api/health")
def health():
    return {"ok": True, "ts": int(time.time())}

@app.get("/api/signals")
def api_signals():
    return read_json(F_SIGNALS, [])

@app.get("/api/positions")
def api_positions():
    return read_json(F_POSITIONS, [])

@app.get("/api/balance")
def api_balance():
    # si le fichier existe on renvoie, sinon on interroge en direct
    data = read_json(F_BALANCE, None)
    if data:
        return data
    ex = get_exchange()
    bal = ex.fetch_balance({"productType": "USDT-FUTURES"})
    total = float(bal.get("total", {}).get("USDT", 0.0))
    data = {"equity_usdt": total, "source": "bitget-futures", "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())}
    write_json(F_BALANCE, data)
    return data

@app.get("/api/risk")
def get_risk():
    data = read_json(F_RISK, {"level": 2, "updated_at": None})
    return data

@app.post("/api/risk")
def set_risk(body: RiskBody, x_api_key: str | None = Header(default=None)):
    check_api_key(x_api_key)
    lvl = max(1, min(3, int(body.level)))
    data = {"level": lvl, "updated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())}
    write_json(F_RISK, data)
    return data

@app.post("/api/close")
def close_position(body: CloseBody, x_api_key: str | None = Header(default=None)):
    check_api_key(x_api_key)
    symbol = (body.symbol or "").upper().replace("/", "")
    if not symbol:
        raise HTTPException(400, "symbol requis")
    if DRY_RUN:
        return {"dry_run": True, "symbol": symbol, "status": "ok"}

    ex = get_exchange()
    market = ex.market(symbol) if symbol in ex.markets else ex.load_markets().get(symbol)
    if not market:
        raise HTTPException(400, f"Unknown symbol {symbol}")

    # stratégie: on ferme en market les positions ouvertes (long/short)
    try:
        pos = [p for p in ex.fetch_positions([symbol]) if p.get("contracts",0)]
    except Exception as e:
        raise HTTPException(500, f"fetch_positions error: {e}")

    orders = []
    for p in pos:
        side = "sell" if float(p.get("contracts",0))>0 else "buy"
        amt = abs(float(p.get("contracts",0)))
        try:
            o = ex.create_order(symbol, "market", side, amt)
            orders.append({"side": side, "qty": amt, "order": o})
        except Exception as e:
            raise HTTPException(500, f"close error: {e}")
    return {"closed": orders}
