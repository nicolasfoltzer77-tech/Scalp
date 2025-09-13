import json, time, pathlib
HEATMAP_PATH = pathlib.Path("/opt/scalp/data/heatmap.json")

def _norm_updated(u):
    try:
        u = int(u)
    except Exception:
        return 0
    return int(u/1000) if u > 10**12 else u

def load_heatmap():
    try:
        with HEATMAP_PATH.open("r") as f:
            data = json.load(f)
        rows = data.get("rows") or []
        if not isinstance(rows, list): rows = []
        updated = _norm_updated(data.get("updated", 0))
        return updated, rows
    except Exception:
        return 0, []

def format_heatmap(rows):
    lines=[]
    for r in rows[:15]:
        sym=r.get("sym","?")
        def trip(tf):
            d=r.get(tf,{})
            return f"{int(d.get('b',0))}/{int(d.get('h',0))}/{int(d.get('s',0))}"
        lines.append(f"{sym:>5} 5m:{trip('5m')} 15m:{trip('15m')} 30m:{trip('30m')}")
    return "```\n"+"\n".join(lines)+"\n```" if lines else None
