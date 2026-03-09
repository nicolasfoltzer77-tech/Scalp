#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Read normalized meta-engine signals from SQLite."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MetaSignal:
    inst_id: str
    meta_score: float
    meta_score_norm: float
    strength: str


def _conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=10000;")
    return conn


def classify_strength(meta_score_norm: float) -> str | None:
    if meta_score_norm >= 0.80:
        return "strong"
    if meta_score_norm >= 0.70:
        return "normal"
    if meta_score_norm >= 0.60:
        return "scalp"
    return None


def read_tradable_meta_signals(
    db_path: Path,
    *,
    limit: int = 10,
    min_norm_score: float = 0.60,
) -> list[MetaSignal]:
    query = """
        SELECT instId, meta_score, meta_score_norm
        FROM v_meta_rank_norm
        WHERE meta_score_norm >= ?
        ORDER BY meta_score_norm DESC
        LIMIT ?
    """

    with _conn(db_path) as conn:
        rows = conn.execute(query, (float(min_norm_score), int(limit))).fetchall()

    signals: list[MetaSignal] = []
    for row in rows:
        inst_id = row["instId"]
        if not inst_id:
            continue
        norm = float(row["meta_score_norm"] or 0.0)
        strength = classify_strength(norm)
        if strength is None:
            continue
        signals.append(
            MetaSignal(
                inst_id=inst_id,
                meta_score=float(row["meta_score"] or 0.0),
                meta_score_norm=norm,
                strength=strength,
            )
        )
    return signals
