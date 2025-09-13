#!/usr/bin/env python3
import os, time, csv, pathlib, sys
import ccxt
from datetime import datetime, timezone

ENV = "/opt/scalp/scalp.env"
OUTDIR = pathlib.Path("/opt/scalp/data/candles")
OUTDIR.mkdir(parents=True, exist_ok=True)

def load_env(path=ENV):
    env={}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line=line.strip()
                if not line or line.startswith("#") or "=" not in line: continue
                k,v=line.split("=",1); env[k.strip()]=v.strip().strip("'").strip('"')
    return env

def client(env):
    exname = env.get("EXCHANGE","bitget").lower()
    if exname!="bitget": raise RuntimeError("Seul bitget est supporté ici")
    key=env.get("BITGET_API_KEY") or env.get("API_KEY")
    sec=env.get("BITGET_API_SECRET") or env.get("API_SECRET")
    pas=env.get("BITGET_API_PASSPHRASE") or env.get("BITGET_PASSPHRASE") or env.get("API_PASSPHRASE")
    return ccxt.bitget({'apiKey':key,'secret':sec,'password':pas})

def base_list():
    # liste “trophée” par défaut
    return ["BTC/USDT","ETH/USDT","SOL/USDT","BNB/USDT","XRP/USDT","DOGE/USDT",
            "ADA/USDT","TRX/USDT","TON/USDT","LINK/USDT","LTC/USDT","ARB/USDT","APT/USDT","SUI/USDT","OP/USDT"]

def symbols_from_top():
    p="/opt/scalp/data/top.json"
    try:
        import json
        if os.path.getsize(p)>0:
            data=json.load(open(p))
            aset=data.get("assets") or []
            if aset: return [a if "/" in a else f"{a}/USDT" for a in aset[:15]]
    except Exception: pass
    return base_list()

def write_csv(sym, rows):
    # rows: list of [ts,open,high,low,close,volume]
    out=OUTDIR/f"{sym.split('/')[0]}_5m.csv"
    with open(out,"w",newline="") as f:
        w=csv.writer(f)
        for r in rows: w.writerow(r)

def fetch_one(ex, sym, limit=120):
    for _ in range(2):
        try:
            o = ex.fetch_ohlcv(sym, timeframe="5m", limit=limit)
            return o
        except Exception as e:
            time.sleep(0.7)
    raise

def main():
    env=load_env()
    ex=client(env)
    syms = symbols_from_top()
    for s in syms:
        rows = fetch_one(ex, s, limit=180)
        write_csv(s, rows)
    # status.json ping
    import json
    pathlib.Path("/opt/scalp/data").mkdir(parents=True, exist_ok=True)
    js={"updated": int(time.time()*1000)}
    open("/opt/scalp/data/status.json","w").write(json.dumps(js))
    print(f"ok rows {len(syms)}")

if __name__=="__main__":
    main()
