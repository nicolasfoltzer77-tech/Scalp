# scalper/signals/current.py
from __future__ import annotations

# Wrapper pour utiliser la stratégie live actuelle en mode "plugin"
from engine.strategy import generate_signal as _generate_signal

def generate_signal(**kwargs):
    """
    Expose la même signature que engine.strategy.generate_signal.
    Sert d’adaptateur pour la factory.
    """
    return _generate_signal(**kwargs)