#!/usr/bin/env python3
import json, os, time, glob
from pathlib import Path
DATA = Path("/opt/scalp/data")
OUT  = Path("/opt/scalp/var/dashboard"); OUT.mkdir(parents=True, exist_ok=True)
items=[]
for p in sorted(glob.glob(str(DATA/"*.{json,jsonl}").replace("{","[").replace("}","]")),
                key=lambda x: os.path.getmtime(x), reverse=True)[:10]:
    st=os.stat(p)
    items.append({"name":os.path.basename(p),
                  "path":p, "size":st.st_size,
                  "mtime":time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(st.st_mtime))})
(Path(OUT/"last10-data.json")).write_text(json.dumps(items, ensure_ascii=False, indent=2))
