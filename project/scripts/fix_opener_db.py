#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FIX opener.db (IDEMPOTENT)

But :
- supprimer les vues cassées qui pointent sur opener_old
- migrer opener vers une table multi-lignes :
    PRIMARY KEY (uid, exec_type, step)
- préserver les données existantes (copie intersection colonnes)
- recréer une vue simple v_opener (non bloquante)

Exécution :
  python3 /opt/scalp/project/scripts/fix_opener_db.py
"""

import sqlite3
import time
from pathlib import Path

ROOT = Path("/opt/scalp/project")
DB = ROOT / "data" / "opener.db"

TARGET_SCHEMA = """
CREATE TABLE opener_new (
    uid TEXT NOT NULL,
    instId TEXT NOT NULL,
    side TEXT NOT NULL,
    qty REAL NOT NULL,
    lev REAL NOT NULL,
    ts_open INTEGER,
    price_exec_open REAL,
    status TEXT NOT NULL,
    exec_type TEXT NOT NULL,
    step INTEGER NOT NULL,
    PRIMARY KEY (uid, exec_type, step)
);
"""

def table_exists(c: sqlite3.Connection, name: str) -> bool:
    r = c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (name,)).fetchone()
    return bool(r)

def view_rows(c: sqlite3.Connection):
    return c.execute("SELECT name, sql FROM sqlite_master WHERE type='view'").fetchall()

def columns(c: sqlite3.Connection, table: str):
    return [r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()]

def main():
    if not DB.exists():
        raise SystemExit(f"DB not found: {DB}")

    c = sqlite3.connect(str(DB), timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=30000;")
    c.execute("PRAGMA foreign_keys=OFF;")

    # 1) Drop any view referencing opener_old (and also stale v_opener)
    for r in view_rows(c):
        name = r["name"]
        sql = (r["sql"] or "").lower()
        if "opener_old" in sql or name.lower() in ("v_opener", "v_opener_monitoring"):
            c.execute(f"DROP VIEW IF EXISTS {name}")

    # 2) Clean leftovers
    c.execute("DROP TABLE IF EXISTS opener_new")

    src_table = None
    if table_exists(c, "opener_old"):
        src_table = "opener_old"
    elif table_exists(c, "opener"):
        src_table = "opener"
    else:
        # DB empty: create target table and view then exit
        c.execute(TARGET_SCHEMA)
        c.execute("ALTER TABLE opener_new RENAME TO opener")
        c.execute("CREATE VIEW IF NOT EXISTS v_opener AS SELECT * FROM opener;")
        c.commit()
        c.close()
        return

    src_cols = set(columns(c, src_table))

    # 3) Create new table
    c.execute(TARGET_SCHEMA)

    # 4) Build safe insert using available columns (defaults otherwise)
    def col(name: str, default_sql: str):
        return name if name in src_cols else default_sql

    uid   = col("uid", "NULL")
    inst  = col("instId", "''")
    side  = col("side", "''")
    qty   = col("qty", "0.0")
    lev   = col("lev", "1.0")
    tsop  = col("ts_open", "NULL")
    pxop  = col("price_exec_open", "NULL")
    stat  = col("status", "''")

    # exec_type / step : si absents, fallback propre
    etype = col("exec_type", "'open'")
    step  = col("step", "0")

    # 5) Copy rows (dedupe by composite key)
    c.execute(f"""
        INSERT OR IGNORE INTO opener_new
        (uid, instId, side, qty, lev, ts_open, price_exec_open, status, exec_type, step)
        SELECT
            {uid}   AS uid,
            {inst}  AS instId,
            {side}  AS side,
            CAST({qty} AS REAL) AS qty,
            CAST({lev} AS REAL) AS lev,
            {tsop}  AS ts_open,
            {pxop}  AS price_exec_open,
            {stat}  AS status,
            {etype} AS exec_type,
            CAST({step} AS INTEGER) AS step
        FROM {src_table}
        WHERE {uid} IS NOT NULL AND TRIM({uid}) <> ''
    """)

    # 6) Backup old opener table (if exists) and swap
    ts = int(time.time())
    if table_exists(c, "opener"):
        c.execute(f"ALTER TABLE opener RENAME TO opener_backup_{ts}")

    c.execute("ALTER TABLE opener_new RENAME TO opener")

    # 7) Minimal view recreated
    c.execute("CREATE VIEW IF NOT EXISTS v_opener AS SELECT * FROM opener;")

    c.execute("PRAGMA foreign_keys=ON;")
    c.commit()
    c.close()

if __name__ == "__main__":
    main()

