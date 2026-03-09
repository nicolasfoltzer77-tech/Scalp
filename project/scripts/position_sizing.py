#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Position sizing based on normalized meta score."""

from __future__ import annotations


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def compute_position_size(base_position_size: float, meta_score_norm: float) -> float:
    score = clamp(float(meta_score_norm), 0.0, 1.0)
    base = max(0.0, float(base_position_size))
    return round(base * score, 8)
