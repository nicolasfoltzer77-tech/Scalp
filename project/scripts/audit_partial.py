#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SCALP — AUDIT PARTIAL (ROBUSTE)
Lecture seule — tolérant aux schémas réels
"""

import sqlite3
import sys
from pathlib import Path

ROOT = Path("/opt/scalp/project")

DBS = {
    "gest":     ROOT / "data/gest.db",
    "follower": ROOT / "data/follower.db",
    "closer":   ROOT / "data/closer.db",
    "exec":     ROOT / "data/exec.db",
}

def conn(p):
    c = sqlite3.connect(str(p))
    c.row_factory = sqlite3.Row
    return c

def table_columns(c, table):
    return [r["name"] for r in c.execute(f"PRAGMA table_info({table})")]

def dump(title, rows):
    print(f"\n=== {title} ===")
    if not rows:
        print("(vide)")
        return
    for r in rows:
        print(dict(r))

def safe_select(c, table, uid):
    cols = table_columns(c, table)
    if "uid" not in cols:
        return []

    sql = f"SELECT {', '.join(cols)} FROM {table} WHERE uid=?"
    return c.execute(sql, (uid,)).fetchall()

def audit(uid: str):
    print("\n==============================")
    print(f"AUDIT UID : {uid}")
    print("==============================")

    for name, db in DBS.items():
        with conn(db) as c:
            try:
                rows = safe_select(c, name, uid)
                dump(name.upper(), rows)
            except Exception as e:
                print(f"\n=== {name.upper()} ===")
                print(f"[ERREUR] {e}")

    print("\n--- FIN AUDIT ---\n")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: audit_partial.py <UID>")
        sys.exit(1)

    audit(sys.argv[1])

