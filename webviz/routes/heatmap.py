from collections import defaultdict
from typing import Dict, List
from fastapi import APIRouter
from webviz.core.paths import resolve_paths, load_json, load_signals_any
from webviz.core.diag import diag_heatmap

router = APIRouter()

def _build_from_signals(items: List[Dict], kmax=3) -> Dict:
    latest={}
    for it in items:
        key=(it["sym"], it["tf"])
        if key not in latest or it["ts"]>latest[key]["ts"]:
            latest[key]=it
    by_sym=defaultdict(list)
    for (sym,tf),it in latest.items():
        by_sym[sym].append(it)
    cells=[]
    for sym,arr in by_sym.items():
        arr.sort(key=lambda x: x["ts"], reverse=True)
        for it in arr[:kmax]:
            v = 1.0 if it["side"]=="BUY" else 0.0
            cells.append({"sym": sym, "tf": it["tf"], "side": it["side"], "v": v})
    cells.sort(key=lambda c: (c["sym"], c["tf"]))
    return {"source":"signals.csv","cells":cells}

@router.get("/heatmap_status")
def heatmap_status():
    return diag_heatmap()

@router.get("/heatmap")
def heatmap():
    p = resolve_paths()
    js = load_json(p["heatmap_json"])
    if isinstance(js, dict) and "cells" in js: return js
    return _build_from_signals(load_signals_any())
