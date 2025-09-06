#!/usr/bin/env python3
import os, json, glob, time
DATA = "/opt/scalp/data"
OUT  = "/opt/scalp/var/dashboard/last10-data.json"

items = []
for p in glob.glob(os.path.join(DATA, "*.[jJ][sS][oO][nN]")) + \
         glob.glob(os.path.join(DATA, "*.jsonl")):
    try:
        st = os.stat(p)
        items.append({
            "name": os.path.basename(p),
            "path": p,
            "size": st.st_size,
            "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(st.st_mtime))
        })
    except Exception:
        pass

items.sort(key=lambda x: x["mtime"], reverse=True)
with open(OUT + ".tmp", "w", encoding="utf-8") as f:
    json.dump(items[:10], f, ensure_ascii=False, separators=(",",":"))
os.replace(OUT + ".tmp", OUT)
print(f"Wrote {OUT} with {min(10,len(items))} items")
