from __future__ import annotations
from pathlib import Path
from datetime import datetime
from workers.io import read_json_safely

def escape_html(s:str)->str:
    return (s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;"))

def _mtime_hhmm(p:Path)->str:
    try:
        return datetime.fromtimestamp(p.stat().st_mtime).strftime("%H%M")
    except Exception:
        return "----"

def fmt_top(js:dict, data_dir:Path)->str:
    assets = js.get("assets",[])[:15]
    listed = ", ".join(a.split("/")[0] for a in assets)
    hhmm = _mtime_hhmm(data_dir/"top.json")
    return f"🏆 {escape_html(listed)}\n• {hhmm}"

def fmt_status(data_dir:Path)->str:
    # simple check: files presence
    top_ok  = (data_dir/"top.json").exists()
    heat_ok = (data_dir/"heatmap.json").exists()
    a = "✅" if top_ok else "❌"
    b = "✅" if heat_ok else "❌"
    return f"{a} top.json { _mtime_hhmm(data_dir/'top.json') } | {b} heatmap.json { _mtime_hhmm(data_dir/'heatmap.json') }"

def _triplet_cell(b:int,h:int,s:int)->str:
    vals = [("b",b),("h",h),("s",s)]
    m = max(v for _,v in vals)
    def styl(k,v): return f"<b>{v}</b>" if v==m else f"<span>{v}</span>"
    return f"{styl('b',b)} {styl('h',h)} {styl('s',s)}"

def fmt_heatmap(js:dict)->str:
    rows = js.get("rows",[])
    # header
    out = ["<b>📊 Heatmap (b/h/s)</b>", "<pre>sym   5m        15m       30m</pre>"]
    lines = []
    for r in rows[:15]:
        sym = r.get("sym","?")
        c5  = r.get("5m",  {"b":0,"h":0,"s":0})
        c15 = r.get("15m", {"b":0,"h":0,"s":0})
        c30 = r.get("30m", {"b":0,"h":0,"s":0})
        line = f"<code>{sym:<4}</code> {_triplet_cell(c5['b'],c5['h'],c5['s'])}   {_triplet_cell(c15['b'],c15['h'],c15['s'])}   {_triplet_cell(c30['b'],c30['h'],c30['s'])}"
        lines.append(line)
    out.extend(lines)
    return "\n".join(out)
