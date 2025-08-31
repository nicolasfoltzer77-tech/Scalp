#!/usr/bin/env python3
# Agrège /opt/scalp/var/trades/*.csv -> /opt/scalp/docs/positions.json
# PnL en USDT. "status": open|closed|paper|liquidated
import csv, json, os, glob, time

TRADES_GLOB = "/opt/scalp/var/trades/*.csv"
OUT = "/opt/scalp/docs/positions.json"
NOW = int(time.time())

def fnum(x): 
    try: return float(str(x).strip())
    except: return 0.0

def fts(x):
    try:
        v=int(float(str(x).strip()))
        return v//1000 if v>10_000_000_000 else v
    except: return 0

def load_fills():
    rows=[]
    for path in sorted(glob.glob(TRADES_GLOB)):
        with open(path, newline="", encoding="utf-8", errors="ignore") as f:
            r=csv.DictReader(f)
            for row in r:
                ts=fts(row.get("timestamp") or row.get("time") or row.get("ts"))
                sym=(row.get("symbol") or row.get("pair") or "").upper()
                side=(row.get("side") or "").upper()
                px=fnum(row.get("price") or row.get("px"))
                qty=fnum(row.get("qty") or row.get("size") or row.get("quantity"))
                if not (ts and sym and side and px and qty): continue
                if side in ("BUY","LONG"): side="LONG"
                elif side in ("SELL","SHORT"): side="SHORT"
                rows.append({"ts":ts,"symbol":sym,"side":side,"price":px,"qty":qty})
    return sorted(rows,key=lambda x:x["ts"])

def build_open_only(fills):
    # Version simple: positions OPEN uniquement (on fermera via un exits.csv si dispo)
    pos={}
    for f in fills:
        k=(f["symbol"],f["side"])
        b=pos.setdefault(k,{"q":0.0,"ws":0.0,"ts":f["ts"]})
        b["q"]+=f["qty"]; b["ws"]+=f["qty"]*f["price"]; b["ts"]=min(b["ts"],f["ts"])
    out=[]
    for (sym,side),b in pos.items():
        if b["q"]>0:
            out.append({
                "open_ts": b["ts"], "close_ts": 0,
                "symbol": sym, "side": side, "qty": round(b["q"],8),
                "entry": round(b["ws"]/b["q"],8), "exit": 0.0,
                "pnl_usdt": 0.0, "status":"open"
            })
    return out

def attach_exits(positions):
    path="/opt/scalp/var/trades/exits.csv"
    if not os.path.exists(path): return positions
    ex=[]
    with open(path, newline="", encoding="utf-8", errors="ignore") as f:
        r=csv.DictReader(f)
        for row in r:
            ex.append({
                "ts": fts(row.get("timestamp") or row.get("time") or row.get("ts")),
                "symbol": (row.get("symbol") or row.get("pair") or "").upper(),
                "side": (row.get("side") or "").upper(),
                "price": fnum(row.get("price") or row.get("px")),
                "qty": fnum(row.get("qty") or row.get("size") or row.get("quantity")),
                "status": (row.get("status") or "closed").lower()
            })
    for p in positions:
        for e in ex:
            if p["symbol"]==e["symbol"] and p["side"]==e["side"] and p["status"]=="open" and e["qty"]>=p["qty"]:
                p["close_ts"]= e["ts"] or NOW
                p["exit"]= round(e["price"],8)
                sgn = 1 if p["side"]=="LONG" else -1
                p["pnl_usdt"]= round(sgn*(p["exit"]-p["entry"])*p["qty"], 4)
                p["status"]= e["status"] if e["status"] in ("closed","paper","liquidated") else "closed"
                break
    return positions

def main():
    fills=load_fills()
    pos=build_open_only(fills)
    pos=attach_exits(pos)
    pos.sort(key=lambda x:(x["close_ts"] or x["open_ts"]), reverse=True)
    os.makedirs(os.path.dirname(OUT),exist_ok=True)
    tmp=OUT+".tmp"; open(tmp,"w").write(json.dumps(pos,separators=(",",":"))); os.replace(tmp,OUT)
    print(f"[positions] wrote {len(pos)} -> {OUT}")

if __name__=="__main__":
    main()
