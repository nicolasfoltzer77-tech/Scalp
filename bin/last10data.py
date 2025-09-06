#!/usr/bin/env python3
import os, json, time, glob
DATA="/opt/scalp/data"
OUT ="/opt/scalp/var/dashboard/last10-data.json"

def ls():
    files=[]
    for pat in ("*.jsonl","*.json"):
        for p in glob.glob(os.path.join(DATA,pat)):
            try:
                st=os.stat(p)
                files.append({"name":os.path.basename(p),
                              "path":p,
                              "size":st.st_size,
                              "mtime":time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))})
            except Exception:
                pass
    files.sort(key=lambda x:os.path.getmtime(os.path.join(DATA,x["name"])), reverse=True)
    return files[:10]

def main():
    items=ls()
    with open(OUT+".tmp","w") as f: json.dump(items,f,ensure_ascii=False, separators=(",",":"))
    os.replace(OUT+".tmp",OUT)

if __name__=="__main__": main()
