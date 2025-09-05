from fastapi import APIRouter, Query
from webviz.core.paths import resolve_paths, load_json

router = APIRouter()

@router.get("/history")
def history(limit: int = Query(100, ge=1, le=1000),
            offset: int = Query(0, ge=0)):
    p = resolve_paths()
    js = load_json(p["history_json"]) or {}
    items = js.get("items") if isinstance(js, dict) else (js if isinstance(js, list) else [])
    if not isinstance(items, list): items=[]
    for it in items:
        if "sym" not in it and "symbol" in it: it["sym"]=it["symbol"]
    total = len(items)
    return {"total": total, "limit": limit, "offset": offset, "items": items[offset:offset+limit]}
