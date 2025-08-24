# engine/config/strategies.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict

def _target_path() -> Path:
    # Fichier promu par jobs/promote.py
    return Path(__file__).resolve().parent / "strategies.yml"

def _load_json_compat(path: Path) -> Dict[str, Any]:
    # On stocke en JSON lisible (extension .yml pour compat) -> lecture JSON
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def load_strategies() -> Dict[str, Dict[str, Any]]:
    """
    Retourne un mapping {"SYMBOL:TF": {params...}, ...}
    Si vide/non trouvé -> {}.
    """
    p = _target_path()
    if not p.exists():
        return {}
    doc = _load_json_compat(p)
    strategies = doc.get("strategies") or {}
    # normalise clés en "BTCUSDT:1m"
    out: Dict[str, Dict[str, Any]] = {}
    for k, v in strategies.items():
        if not isinstance(v, dict):
            continue
        out[str(k).replace("_", "").upper()] = dict(v)
    return out