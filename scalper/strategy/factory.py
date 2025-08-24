# scalper/strategy/factory.py
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

# Enregistreur statique (évite import dynamique fragile)
_REGISTRY: Dict[str, str] = {
    "current": "scalper.strategy.strategies.current:generate_signal",
    # Tu pourras ajouter d'autres stratégies ici, ex:
    # "ema_cross": "scalper.strategy.strategies.ema_cross:generate_signal",
}

def _load_callable(path: str) -> SignalFn:
    """Charge 'module.sub:attr' de manière sûre."""
    if ":" not in path:
        raise ValueError(f"Chemin de callable invalide: {path}")
    module_name, attr = path.split(":", 1)
    mod = importlib.import_module(module_name)
    fn = getattr(mod, attr, None)
    if not callable(fn):
        raise ValueError(f"{attr} n'est pas callable dans {module_name}")
    return fn  # type: ignore

def load_signal(name: str) -> SignalFn:
    name = (name or "").strip().lower()
    if name not in _REGISTRY:
        raise KeyError(f"Stratégie inconnue: '{name}'. Registre: {list(_REGISTRY)}")
    return _load_callable(_REGISTRY[name])

def _read_yaml(path: str) -> dict:
    if yaml is None:
        # Fallback JSON si YAML indispo
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def load_strategies_cfg(path: str) -> dict:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Fichier de config stratégies introuvable: {path}")
    cfg = _read_yaml(path)
    # Normalisation clé
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