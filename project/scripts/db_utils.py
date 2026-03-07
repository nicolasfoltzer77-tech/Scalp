#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""SQLite schema helpers used by runtime pipeline scripts."""

from __future__ import annotations

import logging
import sqlite3


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    names: set[str] = set()
    for row in rows:
        try:
            names.add(row["name"])
        except Exception:
            names.add(row[1])
    return names


def ensure_column(
    conn: sqlite3.Connection,
    table: str,
    column_name: str,
    column_type: str,
    logger: logging.Logger | None = None,
) -> bool:
    """Ensure a column exists; add it safely if missing."""
    try:
        existing = table_columns(conn, table)
        if column_name in existing:
            return False
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_name} {column_type}")
        if logger:
            logger.info("[SCHEMA] added %s.%s (%s)", table, column_name, column_type)
        return True
    except Exception as exc:
        if logger:
            logger.warning("[SCHEMA] failed to add %s.%s: %s", table, column_name, exc)
        return False
