from __future__ import annotations
import os, time
from pathlib import Path
import ccxt

DATA=Path("/opt/scalp/data"); CAND=DATA/"candles"; CAND.mkdir(parents=True,exist_ok=True)
REQ=["BITGET_API_KEY","BITGET_API_SECRET","BITGET_PASSPHRASE"]

def _env(): 
    miss=[k for k in REQ if not os.getenv(k)]
    if miss: raise RuntimeError("Secrets manquants: "+",".join(miss))
def client():
    _env(); return ccxt.bitget({
        "apiKey":os.getenv("BITGET_API_KEY"),
        "secret":os.getenv("BITGET_API_SECRET"),
        "password":os.getenv("BITGET_PASSPHRASE"),
        "enableRateLimit":True,
        "options":{"defaultType":"swap"},
    })
def to_sym(base:str)->str: return f"{base.upper().split('/')[0]}/USDT:USDT"

def get_usdt_balance()->dict:
    ex=client(); bal=ex.fetch_balance(params={"type":"swap"}).get("USDT",{})
    f=float(bal.get("free",0)); u=float(bal.get("used",0)); t=float(bal.get("total",f+u))
    return {"asset":"USDT","free":round(f,2),"used":round(u,2),"total":round(t,2)}

TF={"1m":200,"3m":200,"5m":200,"15m":200,"30m":200,"60m":200}
def fetch_ohlcv_save(base:str, tf:str, limit:int|None=None)->int:
    if tf not in TF: raise ValueError("tf")
    ex=client(); m=to_sym(base); limit=limit or TF[tf]
    rows=ex.fetch_ohlcv(m, timeframe=tf, since=None, limit=limit)
    out=CAND/f"{base.upper().split('/')[0]}_{tf}.csv"
    out.write_text("\n".join(f"{ts}|{o:.8f},{h:.8f},{l:.8f},{c:.8f},{v:.8f}" for ts,o,h,l,c,v in rows[-TF[tf]:]))
    return len(rows)
