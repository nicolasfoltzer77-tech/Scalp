from fastapi import APIRouter, Query
from typing import Optional, List, Dict
from webviz.core.paths import load_signals_any
from webviz.core.diag import diag_signals

router = APIRouter()

def _apply_filters(items: List[Dict], sym: Optional[str], tf: Optional[str], include_hold: bool):
    syms = set(s.strip().upper() for s in sym.split(",")) if sym else None
    tfs  = set(t.strip() for t in tf.split(",")) if tf else None
    out=[]
    for it in items:
        if not include_hold and it["side"]=="HOLD": continue
        if syms and it["sym"].upper() not in syms: continue
        if tfs and it["tf"] not in tfs: continue
        out.append(it)
    return out

@router.get("/signals_status")
def signals_status():
    """Diagnostic détaillé pour la brique 'signals'."""
    return diag_signals()

@router.get("/signals_raw")
def signals_raw(limit: int = Query(100, ge=1, le=2000),
                sym: Optional[str] = None,
                tf: Optional[str] = None,
                include_hold: bool = False):
    items = load_signals_any()
    items = _apply_filters(items, sym, tf, include_hold)
    return items[:limit]

@router.get("/signals")
def signals(limit: int = Query(100, ge=1, le=500),
            offset: int = Query(0, ge=0),
            sym: Optional[str] = None,
            tf: Optional[str] = None,
            include_hold: bool = False):
    items = _apply_filters(load_signals_any(), sym, tf, include_hold)
    total = len(items)
    return {"total": total, "limit": limit, "offset": offset, "items": items[offset:offset+limit]}
