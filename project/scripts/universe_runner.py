#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import sqlite3

try:
    import yaml
except Exception:
    print("[ERR] Missing dependency: PyYAML (pip install pyyaml)", file=sys.stderr)
    sys.exit(1)

CONF_PATH = os.environ.get("UNIVERSE_CONF", "/opt/scalp/project/conf/universe.conf.yaml")

def load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_sql(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def connect(db_path: str) -> sqlite3.Connection:
    con = sqlite3.connect(db_path, timeout=5, isolation_level=None)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    con.execute("PRAGMA busy_timeout=5000;")
    return con

def main() -> int:
    if not os.path.exists(CONF_PATH):
        print(f"[ERR] Missing config: {CONF_PATH}", file=sys.stderr)
        return 1

    cfg = load_yaml(CONF_PATH)

    universe_db = cfg["paths"]["universe_db"]
    sql_dir     = cfg["paths"]["sql_dir"]

    sql_schema = os.path.join(sql_dir, "universe_schema.sql")
    sql_views  = os.path.join(sql_dir, "universe_views.sql")
    sql_update = os.path.join(sql_dir, "universe_update.sql")

    for p in (sql_schema, sql_views, sql_update):
        if not os.path.exists(p):
            print(f"[ERR] Missing SQL file: {p}", file=sys.stderr)
            return 1

    params = {
        "V_MIN":     float(cfg["liquidity"]["volume_24h_min"]),
        "T_MIN":     int(cfg["liquidity"]["ticks_24h_min"]),
        "S_AVG_MAX": float(cfg["spread"]["avg_max"]),
        "S_P95_MAX": float(cfg["spread"]["p95_max"]),
    }

    con = connect(universe_db)

    # bootstrap schema/views (idempotent)
    con.executescript(load_sql(sql_schema))
    con.executescript(load_sql(sql_views))

    # apply rules
    con.execute(load_sql(sql_update), params)

    con.close()

    print(f"[OK] universe rules applied @ {int(time.time())}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

