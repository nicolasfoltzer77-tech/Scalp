#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from typing import Dict, Type, Any, Optional
from .base import StrategyBase
from .ema_atr_v1 import EmaAtrV1

_REGISTRY: Dict[str, Type[StrategyBase]] = {
    "ema_atr_v1": EmaAtrV1,
    # tu pourras ajouter: "two_layer_scalp": TwoLayerScalp, etc.
}

def create(name: str, params: Optional[dict]=None) -> StrategyBase:
    name = (name or "").strip()
    cls = _REGISTRY.get(name)
    if not cls:
        raise KeyError(f"strategy '{name}' not registered")
    return cls(params=params)