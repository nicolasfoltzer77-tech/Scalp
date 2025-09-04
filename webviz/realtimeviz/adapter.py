#!/usr/bin/env python3
from __future__ import annotations
import json, os
from typing import Any, Dict, List

DATA_DIR = "/opt/scalp/data"
REPORTS_DIR = "/opt/scalp/reports"

FILES = {
    "signals":   os.path.join(DATA_DIR, "signals.json"),
    "history":   os.path.join(DATA_DIR, "history.json"),
    "heatmap":   os.path.join(DATA_DIR, "heatmap.json"),
    "watchlist_json": os.path.join(REPORTS_DIR, "watchlist.json"),
    "watchlist_yaml": os.path.join(REPORTS_DIR, "watchlist.yml"),
    "positions_json": os.path.join(REPORTS_DIR, "positions.json"),
    "positions_yaml": os.path.join(REPORTS_DIR, "positions.yml"),
}

def _load_json(path: str, default: Any) -> Any:
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # tolère un fichier qui serait une liste (on l’emballe dans {"items":[...]})
        if isinstance(data, list):
            return {"items": data}
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return default

def sources_info() -> Dict[str, Any]:
    return {
        "as_of": None,
        "files": FILES,
        "hints": {
            "produce_here": DATA_DIR,
            "reports_here": REPORTS_DIR,
        },
    }

def get_signals_snapshot(limit: int = 200, include_hold: bool = True) -> Dict[str, List[Dict]]:
    data = _load_json(FILES["signals"], {"items": []})
    items: List[Dict] = data.get("items", [])
    if not include_hold:
        items = [x for x in items if (x.get("side") or "").upper() != "HOLD"]
    return {"items": items[: max(0, int(limit))]}

def get_history_snapshot(limit: int = 1000) -> Dict[str, List[Dict]]:
    data = _load_json(FILES["history"], {"items": []})
    items: List[Dict] = data.get("items", [])
    return {"items": items[: max(0, int(limit))]}

def get_watchlist_snapshot() -> Dict[str, List[Dict]]:
    data = _load_json(FILES["watchlist_json"], {"items": []})
    return {"items": data.get("items", [])}

def get_heatmap_cells() -> Dict[str, Any]:
    # format libre : on renvoie tel quel (la route /viz/heatmap fait .cells|length)
    return _load_json(FILES["heatmap"], {"cells": []})
