#!/usr/bin/env python3
import sys, csv, json, os

CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else "/opt/scalp/var/dashboard/signals.csv"
OUT_PATH = "/opt/scalp/docs/latest.json"

# pondérations simples pour le score
MAP = {"STRONG_BUY":2, "BUY":1, "HOLD":0, "SELL":-1, "STRONG_SELL":-2}

def parse_details(details:str) -> int:
    if not details: return 0
    s = 0
    # attend "rule=STATE;rule2=STATE..."
    for tok in details.split(";"):
        if "=" in tok:
            _, v = tok.split("=",1)
            s += MAP.get(v.strip().upper(), 0)
        else:
            s += MAP.get(tok.strip().upper(), 0)
    # clamp raisonnable
    if s > 5: s = 5
    if s < -5: s = -5
    return s

def sniff(path):
    with open(path, "rb") as fb:
        sample = fb.read(4096).decode("utf-8", errors="ignore")
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;|\t")
    except Exception:
        return csv.excel

def read_rows(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return []
    dialect = sniff(path)
    out = []
    with open(path, newline="", encoding="utf-8", errors="ignore") as f:
        r = csv.reader(f, dialect)
        for row in r:
            if not row: continue
            while len(row) < 5: row.append("")
            ts_s, sym, tf, sig, det = row[:5]
            try: ts = int(float(str(ts_s).strip()))
            except: 
                # saute une éventuelle ligne d'entête
                if str(ts_s).lower() in ("ts","timestamp","time"): continue
                ts = 0
            sym = (sym or "").strip().upper()
            tf  = (tf  or "").strip()
            sig = (sig or "HOLD").strip().upper()
            det = (det or "").strip()
            if not sym or not tf: continue
            out.append({"ts":ts,"symbol":sym,"tf":tf,"signal":sig,"details":det})
    return out

def latest(rows):
    best={}
    for r in rows:
        k=(r["symbol"], r["tf"])
        if k not in best or r["ts"] >= best[k]["ts"]:
            best[k]=r
    # calcule score
    out=[]
    for r in best.values():
        sc = parse_details(r.get("details",""))
        r = dict(r); r["score"]=sc
        out.append(r)
    # tri lisible
    tf_order={"1m":0,"5m":1,"15m":2,"1h":3,"4h":4,"1d":5}
    out.sort(key=lambda x:(x["symbol"], tf_order.get(x["tf"], 99), x["tf"]))
    return out

def main():
    rows = read_rows(CSV_PATH)
    data = latest(rows)
    json.dump(data if data else [{"ts":0,"symbol":"?","tf":"?","signal":"HOLD","details":"","score":0}],
              sys.stdout, separators=(",",":"))
if __name__=="__main__": main()
