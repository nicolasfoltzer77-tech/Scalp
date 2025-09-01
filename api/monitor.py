# api/monitor.py
from __future__ import annotations
from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from datetime import datetime, timezone
import json
from typing import Optional, Dict, Any
from engine.app_state import AppState

app = FastAPI(title="Scalp Monitor API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def day_str(d: Optional[str]=None) -> str:
    return d or datetime.now(timezone.utc).strftime("%Y%m%d")

def read_jsonl(path: Path, limit: int = 200):
    if not path.exists(): return []
    items = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                items.append(json.loads(line))
            except Exception:
                continue
    return items[-limit:]

@app.get("/api/state")
def get_state():
    return AppState().as_dict()

@app.post("/api/state")
def set_state(payload: Dict[str, Any] = Body(...)):
    st = AppState()
    return st.update(**payload)

@app.get("/api/signals")
def get_signals(day: Optional[str] = None, limit: int = 200):
    p = Path("var")/"signals"/day_str(day)/"signals.jsonl"
    return read_jsonl(p, limit)

@app.get("/api/positions")
def get_positions(day: Optional[str] = None, limit: int = 200):
    p = Path("var")/"positions"/day_str(day)/"positions.jsonl"
    return read_jsonl(p, limit)

@app.get("/api/trades")
def get_trades(day: Optional[str] = None, limit: int = 200):
    p = Path("var")/"trades"/day_str(day)/"trades.jsonl"
    return read_jsonl(p, limit)
