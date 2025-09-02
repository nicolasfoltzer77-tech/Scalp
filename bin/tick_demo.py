#!/usr/bin/env python3
import time, json, os, uuid, datetime as dt
BASE = "/opt/scalp/var/signals"
os.makedirs(BASE, exist_ok=True)

def write_signal(sig):
    d = dt.datetime.utcnow().strftime("%Y%m%d")
    p = f"{BASE}/{d}"
    os.makedirs(p, exist_ok=True)
    f = f"{p}/signals.jsonl"  # JSONL pour append simple
    with open(f, "a") as fh:
        fh.write(json.dumps(sig, ensure_ascii=False) + "\n")

side = "BUY"
price = 60000.0
qty = 0.01  # 0.01 BTC -> qty_usdt ~ 600 USDT

while True:
    now = dt.datetime.utcnow().replace(microsecond=0).isoformat()+"+00:00"
    sig = {
        "ts": now,
        "run_id": str(uuid.uuid4()),
        "symbol": "BTCUSDT",
        "side": side,                  # "BUY" ou "SELL"
        "score": 0.71,
        "qty": qty,
        "entry": {"type":"market","price_ref": price},
        "quality": {"components":{"rsi":62,"adx":24,"macd_hist":0.9,"obv_slope":0.35}},
        "strategy":{"name":"TwoLayer_Scalp","timeframe":"1m","version":"1.0"},
        "notes":"demo"
    }
    write_signal(sig)
    print("emit", now, side, "@", price)
    # petite variation
    price += 5 if side=="BUY" else -5
    side = "SELL" if side=="BUY" else "BUY"
    time.sleep(15)
