from __future__ import annotations
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from .models import HeatMapPayload, HeatCell, load_watchlist, save_watchlist, strip_quote_usdt, make_demo_payload
import time

router = APIRouter()

_STATE: Dict[str, Any] = {
    "payload": None,
}

def _filtered_sorted(payload: HeatMapPayload) -> HeatMapPayload:
    """Filtre par watchlist et trie décroissant par score."""
    if not payload:
        return HeatMapPayload(cells=[])
    wl = set(load_watchlist())
    cells = [
        HeatCell(**c.model_dump(), display=strip_quote_usdt(c.pair))
        for c in payload.cells
        if c.pair in wl
    ]
    cells.sort(key=lambda c: c.score, reverse=True)
    return HeatMapPayload(as_of=payload.as_of, cells=cells)

@router.get("/heatmap")
def get_heatmap() -> Dict[str, Any]:
    payload: HeatMapPayload | None = _STATE.get("payload")
    if payload is None:
        payload = make_demo_payload()
        _STATE["payload"] = payload
    filt = _filtered_sorted(payload)
    return {"as_of": filt.as_of, "cells": [c.model_dump() for c in filt.cells]}

@router.post("/heatmap")
def post_heatmap(p: HeatMapPayload) -> Dict[str, Any]:
    _STATE["payload"] = p
    return {"status": "ok", "count": len(p.cells), "as_of": p.as_of}

@router.post("/heatmap/seed_demo")
def post_heatmap_seed_demo() -> Dict[str, Any]:
    p = make_demo_payload()
    _STATE["payload"] = p
    return {"status": "ok", "count": len(p.cells), "as_of": p.as_of}

@router.get("/watchlist")
def get_watchlist() -> Dict[str, Any]:
    return {"watchlist": load_watchlist()}

@router.put("/watchlist")
def put_watchlist(body: Dict[str, List[str]]) -> Dict[str, Any]:
    pairs = body.get("watchlist", [])
    wl = save_watchlist(pairs)
    # Refiltrer l'état courant si présent
    if _STATE.get("payload"):
        _STATE["payload"] = HeatMapPayload(
            as_of=time.time(),
            cells=[c for c in _STATE["payload"].cells if c.pair in set(wl)]
        )
    return {"status": "ok", "watchlist": wl}
