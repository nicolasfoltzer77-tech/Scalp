# /opt/scalp/viz_main.py  — rtviz-0.4

from __future__ import annotations
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from datetime import datetime, timezone
import asyncio, json, os

# --- Constantes de chemins
DATA_DIR    = "/opt/scalp/data"
REPORTS_DIR = "/opt/scalp/reports"

PATH_SIGNALS  = os.path.join(DATA_DIR, "signals.json")
PATH_HISTORY  = os.path.join(DATA_DIR, "history.json")
PATH_HEATMAP  = os.path.join(DATA_DIR, "heatmap.json")

PATH_WL_JSON  = os.path.join(REPORTS_DIR, "watchlist.json")
PATH_WL_YAML  = os.path.join(REPORTS_DIR, "watchlist.yml")
PATH_POS_JSON = os.path.join(REPORTS_DIR, "positions.json")
PATH_POS_YAML = os.path.join(REPORTS_DIR, "positions.yml")

VER = "rtviz-0.4"

# --- Utils
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def sse_pack(data: dict, event: str | None = None) -> bytes:
    payload = json.dumps(data, separators=(",", ":"))
    head = f"event: {event}\n" if event else ""
    return (head + f"data: {payload}\n\n").encode("utf-8")

def _read_text(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None

def read_json(path: str, default):
    try:
        raw = _read_text(path)
        if not raw:
            return default
        return json.loads(raw)
    except Exception:
        return default

def _read_yaml(path: str):
    try:
        import yaml  # facultatif
        txt = _read_text(path)
        if not txt:
            return None
        return yaml.safe_load(txt)
    except Exception:
        return None

def as_items_array(obj) -> list:
    """
    Retourne une liste d'objets à partir de différents formats:
      - liste brute
      - dict {"items":[...]}
    """
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        val = obj.get("items")
        return val if isinstance(val, list) else []
    return []

# --- Snapshots simples (sans dépendance "adapter")
def get_signals_snapshot(limit: int = 200, include_hold: bool = True) -> dict:
    raw = read_json(PATH_SIGNALS, [])
    items = as_items_array(raw)
    # Filtre optionnel des HOLD
    if not include_hold:
        items = [x for x in items if str(x.get("side","")).upper() != "HOLD"]
    return {"as_of": now_iso(), "items": items[: max(0, int(limit))]}

def get_history_snapshot(limit: int = 1000) -> dict:
    raw = read_json(PATH_HISTORY, [])
    items = as_items_array(raw)
    return {"as_of": now_iso(), "items": items[: max(0, int(limit))]}

def get_watchlist_snapshot() -> dict:
    data = read_json(PATH_WL_JSON, None)
    if data is None:
        data = _read_yaml(PATH_WL_YAML) or {}
    items = []
    # formats tolérés: {"watchlist":[...]} ou {"items":[...]} ou liste brute
    if isinstance(data, dict):
        if isinstance(data.get("watchlist"), list):
            items = data["watchlist"]
        else:
            items = as_items_array(data)
    elif isinstance(data, list):
        items = data
    return {"as_of": now_iso(), "items": items}

def get_positions_snapshot() -> dict:
    data = read_json(PATH_POS_JSON, None)
    if data is None:
        data = _read_yaml(PATH_POS_YAML) or {}
    items = []
    # formats tolérés: {"positions":[...]} / {"items":[...]} / liste brute
    if isinstance(data, dict):
        if isinstance(data.get("positions"), list):
            items = data["positions"]
        else:
            items = as_items_array(data)
    elif isinstance(data, list):
        items = data
    return {"as_of": now_iso(), "items": items}

def get_heatmap() -> dict:
    # Accepte {"cells":[...]}, liste brute, ou dict arbitraire.
    raw = read_json(PATH_HEATMAP, {"cells": []})
    cells_in = raw if isinstance(raw, list) else raw.get("cells", [])
    if not isinstance(cells_in, list):
        cells_in = []

    norm = []
    for c in cells_in:
        if isinstance(c, dict):
            sym = c.get("sym") or c.get("symbol")
            tf  = c.get("tf")  or c.get("timeframe") or c.get("tfm")
            # Plusieurs clés possibles pour la valeur
            val = c.get("val")
            if val is None: val = c.get("v")
            if val is None: val = c.get("value")
            if val is None: val = c.get("score")
            try:
                if sym and tf is not None and val is not None:
                    v = float(val)
                    v = 0.0 if v < 0 else (1.0 if v > 1 else v)
                    norm.append({"sym": str(sym), "tf": str(tf), "val": v})
            except Exception:
                pass
        elif isinstance(c, (list, tuple)) and len(c) >= 3:
            try:
                v = float(c[2]); v = 0 if v < 0 else (1 if v > 1 else v)
                norm.append({"sym": str(c[0]), "tf": str(c[1]), "val": v})
            except Exception:
                pass

    return {"as_of": now_iso(), "cells": norm}

# --- FastAPI
app = FastAPI(title="SCALP-rtviz", version=VER)

@app.get("/viz/hello")
def viz_hello():
    return {
        "ok": True, "ver": VER, "ts": now_iso(),
        "as_of": now_iso(),
        "files": {
            "signals": PATH_SIGNALS,
            "history": PATH_HISTORY,
            "heatmap": PATH_HEATMAP,
            "watchlist_json": PATH_WL_JSON,
            "watchlist_yaml": PATH_WL_YAML,
            "positions_json": PATH_POS_JSON,
            "positions_yaml": PATH_POS_YAML,
        },
        "hints": {"produce_here": DATA_DIR, "reports_here": REPORTS_DIR},
    }

@app.get("/viz/test")
def viz_test():
    return {"ok": True, "ver": VER}

@app.get("/viz/heatmap")
def viz_heatmap():
    return get_heatmap()

@app.get("/viz/stream")
async def viz_stream():
    async def gen():
        # ping immédiat
        yield sse_pack({"type": "ping", "ts": now_iso()}, "ping")
        # premier push de signaux
        snap = get_signals_snapshot(limit=200, include_hold=True)
        yield sse_pack({"type": "signals", **snap}, "signals")
        # pings périodiques
        while True:
            await asyncio.sleep(2.0)
            yield sse_pack({"type": "ping", "ts": now_iso()}, "ping")
    return StreamingResponse(gen(), media_type="text/event-stream")

# --- API "utiles" pour l'UI
@app.get("/api/signals")
async def api_signals(limit: int = 200, include_hold: bool = True):
    return JSONResponse(get_signals_snapshot(limit=limit, include_hold=include_hold))

@app.get("/api/history")
async def api_history(limit: int = 1000):
    return JSONResponse(get_history_snapshot(limit=limit))

@app.get("/api/watchlist")
async def api_watchlist():
    return JSONResponse(get_watchlist_snapshot())

@app.get("/api/positions")
async def api_positions():
    return JSONResponse(get_positions_snapshot())
