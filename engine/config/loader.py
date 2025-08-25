# engine/config/loader.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

# PyYAML est préférable (format YAML "humain"). On garde un fallback JSON.
try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

# ---------------------------------------------------------------------
# Emplacement du fichier de configuration versionné dans le repo
# ---------------------------------------------------------------------
_CFG_PATH = Path(__file__).resolve().parent / "config.yaml"

# Valeurs par défaut (si une clé manque dans config.yaml)
_DEFAULTS: Dict[str, Any] = {
    "runtime": {
        "timeframe": "1m",
        "refresh_secs": 5,
        "data_dir": "/notebooks/scalp_data/data",
        "reports_dir": "/notebooks/scalp_data/reports",
        "logs_dir": "/notebooks/scalp_data/logs",
    },
    "watchlist": {
        "top": 10,
        "score_tf": "5m",
        "backfill_tfs": ["1m", "5m", "15m"],
        "backfill_limit": 1500,
    },
    "maintainer": {
        "enable": True,
        "interval_secs": 43200,          # 12h
        "seed_tfs": ["1m"],
        "ttl_bars_experimental": 120,
    },
}

# Cache en mémoire pour éviter de relire le fichier à chaque appel
_CFG_CACHE: Dict[str, Any] | None = None


# ---------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------
def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Fusion récursive (override > base)."""
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)  # type: ignore[index]
        else:
            out[k] = v
    return out


def _read_yaml_or_json(path: Path) -> Dict[str, Any]:
    """Lit config.yaml. Accepte YAML classique ou JSON 'lisible'."""
    if not path.exists():
        return {}
    txt = path.read_text(encoding="utf-8")
    # 1) tenter YAML si dispo
    if yaml is not None:
        try:
            doc = yaml.safe_load(txt) or {}
            if isinstance(doc, dict):
                return doc  # type: ignore[return-value]
        except Exception:
            pass
    # 2) fallback JSON
    try:
        doc = json.loads(txt) or {}
        if isinstance(doc, dict):
            return doc  # type: ignore[return-value]
    except Exception:
        pass
    return {}


# ---------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------
def cfg_path() -> Path:
    """Retourne le chemin du fichier de config dans le repo."""
    return _CFG_PATH


def load_config(reload: bool = False) -> Dict[str, Any]:
    """
    Charge la configuration fusionnée (defaults + engine/config/config.yaml).
    Utilise un cache en mémoire; passer reload=True pour forcer la relecture.
    """
    global _CFG_CACHE
    if _CFG_CACHE is not None and not reload:
        return _CFG_CACHE

    # Lire le document (vide si absent/illisible)
    doc = _read_yaml_or_json(_CFG_PATH)

    # Fusion récursive avec les defaults
    merged = _deep_merge(_DEFAULTS, doc)

    # Normalisations légères
    # - watchlist.backfill_tfs peut être une chaîne "1m,5m" -> liste
    wl = merged.get("watchlist", {})
    if isinstance(wl, dict):
        tfs = wl.get("backfill_tfs")
        if isinstance(tfs, str):
            wl["backfill_tfs"] = [t.strip() for t in tfs.split(",") if t.strip()]
        merged["watchlist"] = wl

    _CFG_CACHE = merged
    return merged


__all__ = ["load_config", "cfg_path"]