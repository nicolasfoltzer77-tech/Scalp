#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from typing import Dict, Any

def resolve_strategy_params(rt: Dict[str, Any]) -> Dict[str, Any]:
    """
    Params finaux = strategy_params_base ∪ strategy_profiles[risk_mode]
    """
    base = dict(rt.get("strategy_params_base") or {})
    profiles = rt.get("strategy_profiles") or {}
    mode = (rt.get("risk_mode") or "normal").strip().lower()
    prof = dict(profiles.get(mode) or {})
    return {**base, **prof}