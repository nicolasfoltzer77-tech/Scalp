# scalper/signals/factory.py
from __future__ import annotations

import importlib
import importlib.util
from typing import Callable, Dict, Optional

SignalFn = Callable[..., object]

# Mapping symbolique -> module (tu peux en ajouter librement)
_REGISTRY: Dict[str, str] = {
    # Stratégie "actuelle" (renvoie scalper.strategy.generate_signal)
    "current": "scalper.signals.current",

    # Exemples de plugins (crée les fichiers si tu veux les utiliser)
    "ema_cross": "scalper.signals.ema_cross",
    "vwap_break": "scalper.signals.vwap_break",
}

def _module_exists(modname: str) -> bool:
    return importlib.util.find_spec(modname) is not None

def load_signal(name: str, *, default: str = "current") -> SignalFn:
    """
    Charge et retourne une fonction `generate_signal` pour la stratégie `name`.
    Si le module n'existe pas, on retombe sur `default` (courant: 'current').
    """
    target = _REGISTRY.get(name, _REGISTRY.get(default, "scalper.signals.current"))
    if not _module_exists(target):
        # fallback direct sur 'current'
        target = _REGISTRY.get(default, "scalper.signals.current")

    mod = importlib.import_module(target)
    fn = getattr(mod, "generate_signal", None)
    if not callable(fn):
        # dernier filet de sécurité : stratégie live directe
        from scalper.strategy import generate_signal as live_generate
        return live_generate
    return fn

def available_strategies() -> Dict[str, str]:
    """
    Retourne {nom: 'ok'/'missing'} pour afficher ce qui est disponible.
    """
    out: Dict[str, str] = {}
    for name, mod in _REGISTRY.items():
        out[name] = "ok" if _module_exists(mod) else "missing"
    return out