# engine/config/loader.py (ajoute/replace ce bloc d’aides)
from __future__ import annotations
import json, os
from pathlib import Path
from typing import Any, Dict

_CFG_PATH = Path(__file__).resolve().parent / "config.yaml"

_DEFAULTS: Dict[str, Any] = {
    "runtime": {
        "timeframe": "1m",
        "refresh_secs": 5,
        "data_dir": "/notebooks/scalp_data/data",
        "reports_dir": "/notebooks/scalp_data/reports",
    },
    "watchlist": {
        "top": 10,
        "score_tf": "5m",
        "backfill_tfs": ["1m", "5m", "15m"],
        "backfill_limit": 1500,
    },
    "maintainer": {
        "enable": True,
        "interval_secs": 43200,
        "seed_tfs": ["1m"],
        "ttl_bars_experimental": 120,
    },
}

def _read_jsonish(p: Path) -> Dict[str, Any]:
    if not p.exists():
        return {}
    try:
        # notre "yaml" est du JSON lisible
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out

def load_config() -> Dict[str, Any]:
    doc = _read_jsonish(_CFG_PATH)
    return _deep_merge(_DEFAULTS, doc)

# optionnel: alias pour compenser variables d'env historiques (on garde)
def apply_env_aliases() -> None:
    # pas de logique nécessaire ici pour ces nouveaux paramètres
    return