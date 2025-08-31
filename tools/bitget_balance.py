#!/usr/bin/env python3
import json, os, time

OUT="/opt/scalp/docs/bitget_balance.json"
OVERRIDE_FILE=os.getenv("BAL_OVERRIDE", "/opt/scalp/var/exchange/balance.usdt")

def write(usdt: float):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    data={"equity_usdt": round(float(usdt), 2), "generated_at": time.strftime("%F %T UTC", time.gmtime())}
    tmp=OUT+".tmp"
    with open(tmp,"w") as f: json.dump(data,f,separators=(",",":"))
    os.replace(tmp,OUT)
    print(f"[balance] {data}")

def try_override():
    try:
        if OVERRIDE_FILE and os.path.exists(OVERRIDE_FILE):
            return float(open(OVERRIDE_FILE).read().strip())
    except: pass
    return None

def try_api():
    # Laisse 0 si pas de clés ; si tu veux l’API on branchera proprement plus tard.
    return None

if __name__=="__main__":
    val = try_override()
    if val is None: val = try_api()
    if val is None: val = 0.0
    write(val)
