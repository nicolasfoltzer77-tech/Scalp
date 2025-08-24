# engine/config/watchlist.py
from __future__ import annotations
import json, os, time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

from engine.config.loader import load_config
from engine.pairs.selector import PairMetrics

def _watchlist_path() -> Path:
    # Fichier versionné ou non ? -> dans DATA_ROOT/reports (hors repo)
    cfg = load_config()
    p = Path(cfg["runtime"]["reports_dir"]) / "watchlist.yml"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

def save_watchlist(pairs: List[PairMetrics], *, timestamp: int | None = None) -> Path:
    path = _watchlist_path()
    doc = {
        "updated_at": int(timestamp or time.time()),
        "top": [asdict(p) for p in pairs],
    }
    # json lisible (compat .yml reader simple)
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return path

def load_watchlist() -> Dict[str, Any]:
    p = _watchlist_path()
    if not p.exists():
        return {"updated_at": 0, "top": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"updated_at": 0, "top": []}