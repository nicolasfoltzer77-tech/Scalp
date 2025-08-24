# scalper/signals/factory.py
from __future__ import annotations
from typing import Callable, Dict, Any
import importlib
import os
import json

try:
    import yaml  # type: ignore
except Exception:
    yaml = None  # type: ignore

SignalFn = Callable[..., Any]

# IMPORTANT : on pointe par défaut sur TA stratégie actuelle dans scalper/strategy.py
_REGISTRY: Dict[str, str] = {
    "current": "scalper.strategy:generate_signal",
    # Tu pourras ajouter d'autres stratégies ici, par ex :
    # "ema_cross": "scalper.strategies.ema_cross:generate_signal",
}

def _load_callable(path: str) -> SignalFn:
    if ":" not in path:
        raise ValueError(f"Chemin callable invalide: {path}")
    module_name, attr = path.split(":", 1)
    mod = importlib.import_module(module_name)
    fn = getattr(mod, attr, None)
    if not callable(fn):
        raise ValueError(f"{attr} n'est pas callable dans {module_name}")
    return fn  # type: ignore

def load_signal(name: str) -> SignalFn:
    key = (name or "").strip().lower()
    if key not in _REGISTRY:
        raise KeyError(f"Stratégie inconnue: '{name}'. Registre: {list(_REGISTRY)}")
    return _load_callable(_REGISTRY[key])

def _read_yaml(path: str) -> dict:
    if yaml is None:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def load_strategies_cfg(path: str | None) -> dict:
    """
    Charge le mapping (symbole, timeframe) -> nom de stratégie.
    Si le fichier n'existe pas, retourne une config par défaut fonctionnelle.
    """
    default_cfg = {"default": "current", "by_timeframe": {}, "by_symbol": {}}
    if not path:
        return default_cfg
    if not os.path.isfile(path):
        # Pas de fichier ? On continue avec les valeurs par défaut.
        return default_cfg
    cfg = _read_yaml(path)
    cfg.setdefault("default", "current")
    cfg.setdefault("by_timeframe", {})
    cfg.setdefault("by_symbol", {})
    return cfg

def resolve_strategy_name(symbol: str, timeframe: str, cfg: dict) -> str:
    symbol = (symbol or "").upper()
    timeframe = (timeframe or "").lower()
    return (
        cfg.get("by_symbol", {}).get(symbol, {}).get(timeframe)
        or cfg.get("by_timeframe", {}).get(timeframe)
        or cfg.get("default", "current")
    )

def resolve_signal_fn(symbol: str, timeframe: str, cfg: dict) -> SignalFn:
    return load_signal(resolve_strategy_name(symbol, timeframe, cfg))