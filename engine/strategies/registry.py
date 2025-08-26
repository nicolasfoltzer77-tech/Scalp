#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Strategy registry: map strategy name -> class
"""

from __future__ import annotations
from typing import Dict, Type
from .base import StrategyBase
from .ema_atr_v1 import EmaAtrV1  # <- casse corrigée

# Registry of available strategies
_REGISTRY: Dict[str, Type[StrategyBase]] = {
    "ema_atr_v1": EmaAtrV1,
    # "two_layer_lite": TwoLayerLite,  # prochainement
}

def create(name: str, params: dict) -> StrategyBase:
    if name not in _REGISTRY:
        raise ValueError(f"Unknown strategy: {name} · disponibles: {list(_REGISTRY)}")
    return _REGISTRY[name](params)

def list_strategies() -> list[str]:
    return list(_REGISTRY.keys())