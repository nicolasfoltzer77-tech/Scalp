#!/usr/bin/env python3
import csv, json, os, collections

SRC="/opt/scalp/var/dashboard/signals.csv"
OUT="/opt/scalp/docs/scores.json"

W=[3,2,1,1,1]  # poids 5 derniers
MAP={"BUY":1,"SELL":-1,"HOLD":0}

def main():
    by=collections.defaultdict(list)  # (sym,tf)->[(ts,signal)]
    if not os.path.exists(SRC):
        open(OUT,"w").write("{}"); return
    with open(SRC, newline="", encoding="utf-8", errors="ignore") as f:
        r=csv.reader(f)
        for row in r:
            # ts,symbol,tf,signal,details
            if len(row)<4: continue
            ts,sym,tf,signal=row[0],row[1].upper(),row[2],row[3].upper()
            by[(sym,tf)].append((int(float(ts)), signal))
    out={}
    for (sym,tf),arr in by.items():
        arr=sorted(arr)[-5:]
        vals=[MAP.get(s,0) for _,s in arr]
        # pad left
        vals=[0]*(5-len(vals))+vals
        score=sum(v*w for v,w in zip(vals,W))
        # bornage approximatif -> [-6..+6], on ramène à [-3..+3]
        score=round(max(-3, min(3, score/2)))
        out.setdefault(sym, {})[tf]=score
    tmp=OUT+".tmp"; open(tmp,"w").write(json.dumps(out,separators=(",",":"))); os.replace(tmp,OUT)

if __name__=="__main__":
    main()
