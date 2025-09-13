#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Calcule la heatmap b/h/s (0..9) pour 5m, 15m, 30m
à partir des CSV OHLCV: /opt/scalp/data/candles/{SYM}_{TF}.csv
Format attendu (sans header): ts,open,high,low,close,volume
Écrit : /opt/scalp/data/heatmap.json
"""
import os, csv, math, json, time, tempfile, fcntl
from statistics import mean

DATA_DIR = "/opt/scalp/data/candles"
OUT_JSON = "/opt/scalp/data/heatmap.json"
LOCK = "/opt/scalp/data/heatmap.lock"

SYMS = ["ADA","APT","ARB","BNB","BTC","DOGE","ETH","LINK",
        "LTC","OP","SOL","SUI","TON","TRX","XRP"]
TFS  = ["5m","15m","30m"]

# ----- petites utils -----
def ema(series, n):
    if not series: return []
    k = 2/(n+1)
    e = [series[0]]
    for x in series[1:]:
        e.append(e[-1] + k*(x - e[-1]))
    return e

def rsi14(closes, period=14):
    if len(closes) < period+1: return [50.0]*len(closes)
    gains, losses = [], []
    for i in range(1, period+1):
        ch = closes[i]-closes[i-1]
        gains.append(max(ch,0)); losses.append(max(-ch,0))
    avg_gain, avg_loss = mean(gains), mean(losses)
    rsis = [50.0]*(period)  # padding
    for i in range(period+1,len(closes)):
        ch = closes[i]-closes[i-1]
        gain = max(ch,0); loss = max(-ch,0)
        avg_gain = (avg_gain*(period-1)+gain)/period
        avg_loss = (avg_loss*(period-1)+loss)/period
        rs = (avg_gain/avg_loss) if avg_loss>0 else 999
        rsi = 100 - (100/(1+rs))
        rsis.append(rsi)
    if len(rsis)<len(closes):
        rsis += [rsis[-1]]*(len(closes)-len(rsis))
    return rsis

def atr14(highs,lows,closes,period=14):
    if len(closes) < period+1: return [0.0]*len(closes)
    trs=[highs[0]-lows[0]]
    for i in range(1,len(closes)):
        tr=max(highs[i]-lows[i],
               abs(highs[i]-closes[i-1]),
               abs(lows[i]-closes[i-1]))
        trs.append(tr)
    a=[mean(trs[1:period+1])]
    for tr in trs[period+1:]:
        a.append(((a[-1]*(period-1))+tr)/period)
    a=[0.0]*(len(closes)-len(a))+a
    return a

def read_tail_csv(path, maxrows=400):
    if not os.path.exists(path): return []
    # lecture tail légère
    with open(path,"r") as f:
        rows=f.readlines()[-maxrows:]
    out=[]
    for r in rows:
        p=r.strip().split(",")
        if len(p)<6: continue
        try:
            ts=int(p[0]); o=float(p[1]); h=float(p[2]); l=float(p[3]); c=float(p[4]); v=float(p[5])
            out.append((ts,o,h,l,c,v))
        except: continue
    return out

def score_side(b,h,s,total=9):
    # clamp + normalise à somme=total
    b=max(0,round(b)); h=max(0,round(h)); s=max(0,round(s))
    sm=b+h+s
    if sm==0: h=total; return b,h,s
    if sm!=total:
        # redistribue sur la plus forte composante
        diff=total-sm
        if b>=max(h,s): b+=diff
        elif s>=max(b,h): s+=diff
        else: h+=diff
    return int(b),int(h),int(s)

# ----- logique de signal -----
def compute_for_closes_highs_lows_vol(closes, highs, lows, vols):
    n=len(closes)
    if n<50:  # trop court
        return 0,9,0

    ema9 = ema(closes,9)
    ema20 = ema(closes,20)
    rsi = rsi14(closes,14)
    atr = atr14(highs,lows,closes,14)

    c=closes[-1]
    e9, e20 = ema9[-1], ema20[-1]
    r = rsi[-1]
    v = vols[-1]
    v_avg = mean(vols[-60:]) if n>=60 else mean(vols)
    atrp = (atr[-1]/c*100) if c>0 else 0

    b=h=s=0.0

    # 1) momentum EMA cross
    if e9>e20: b+=3
    elif e9<e20: s+=3
    else: h+=2

    # 2) RSI bandes
    if r>=60: b+=2
    elif r<=40: s+=2
    else: h+=2

    # 3) position vs EMA20
    if c>e20: b+=1
    elif c<e20: s+=1
    else: h+=1

    # 4) volume spike
    if v_avg>0 and v>=1.3*v_avg:
        if c>=closes[-2]: b+=2
        else: s+=2
    else:
        h+=1

    # 5) volatilité/ATR (filtre)
    if atrp>=0.8:
        # favorise la direction momentum
        if e9>e20: b+=1
        elif e9<e20: s+=1
        else: h+=1
    else:
        h+=1

    return score_side(b,h,s)

def calc_symbol(sym, tf):
    path = os.path.join(DATA_DIR, f"{sym}_{tf}.csv")
    rows = read_tail_csv(path)
    if not rows:
        return {"b":0,"h":9,"s":0}
    _,o,h,l,c,v = zip(*rows)
    b,h_,s = compute_for_closes_highs_lows_vol(list(c), list(h), list(l), list(v))
    return {"b":b,"h":h_,"s":s}

def build_heatmap():
    rows=[]
    for sym in SYMS:
        entry={"sym":sym}
        for tf in TFS:
            entry[tf] = calc_symbol(sym, tf)
        rows.append(entry)
    return {"updated": int(time.time()*1000), "rows": rows}

def atomic_write(path, data: bytes):
    d=os.path.dirname(path)
    fd,tmp = tempfile.mkstemp(prefix=".hm.",dir=d)
    with os.fdopen(fd,"wb") as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)

def main():
    obj = build_heatmap()
    payload = json.dumps(obj, ensure_ascii=False, separators=(",",":")).encode()
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    # lock fichier pour éviter races avec lecteurs/écrivains
    with open(LOCK,"w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        atomic_write(OUT_JSON, payload)
        fcntl.flock(lf, fcntl.LOCK_UN)
    print(f"heatmap: wrote {len(obj['rows'])} rows -> {OUT_JSON}")

if __name__ == "__main__":
    main()
