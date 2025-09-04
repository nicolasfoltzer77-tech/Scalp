#!/usr/bin/env python3
from __future__ import annotations
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
import csv, os, json, asyncio
from datetime import datetime, timezone
from typing import List, Dict

app = FastAPI(title="SCALP-rtviz", version="0.5")

CSV_SIGNALS = "/opt/scalp/var/dashboard/signals.csv"

def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _load_csv(limit:int=2000) -> List[Dict]:
    """Lit le CSV et renvoie les N dernières lignes MAPPÉES pour l'UI."""
    if not os.path.exists(CSV_SIGNALS):
        return []

    rows: List[Dict] = []
    with open(CSV_SIGNALS, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            # ts dans le CSV = epoch (s) ? (ms) ? → on normalise en secondes (int)
            raw_ts = r.get("ts", "0")
            try:
                ts = int(float(raw_ts))
                if ts > 10**12:  # ms
                    ts //= 1000
            except Exception:
                ts = 0

            # ==== MAPPING attendu par la UI ====
            rows.append({
                "ts": ts,                       # int (epoch seconds)
                "sym": r.get("symbol",""),      # ex: BTCUSDT
                "side": r.get("signal",""),     # ex: BUY/SELL/HOLD
                "score": 0.0,                   # placeholder (pas dispo dans le CSV)
                "entry": r.get("details","") or r.get("tf",""),
                # on garde aussi les champs bruts si besoin plus tard
                "tf": r.get("tf",""),
                "details": r.get("details",""),
            })

    # on garde les plus récentes (CSV croissant → on prend la fin)
    rows = rows[-limit:]
    # ordre décroissant (récent → ancien) pour l’affichage
    rows.sort(key=lambda x: x["ts"], reverse=True)
    return rows

@app.get("/viz/hello")
def viz_hello():
    return {"ok": True, "ver": "rtviz-0.5", "ts": _utcnow_iso()}

@app.get("/viz/test")
def viz_test():
    return {"ok": True, "ver": "rtviz-0.5", "ts": _utcnow_iso()}

@app.get("/api/signals")
def api_signals():
    # Flux récent pour le panneau “Signaux récents”
    return JSONResponse({"items": _load_csv(limit=200)})

@app.get("/api/history")
def api_history():
    # Historique plus large
    return JSONResponse({"items": _load_csv(limit=1000)})

@app.get("/viz/stream")
async def viz_stream():
    # SSE pour rafraîchir le tableau sans recharger la page
    async def gen():
        while True:
            payload = {"items": _load_csv(limit=200)}
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(3)
    return StreamingResponse(gen(), media_type="text/event-stream")

# (optionnel) endpoint heatmap minimal (vide pour l’instant)
@app.get("/viz/heatmap")
def viz_heatmap():
    return {"cells": []}
