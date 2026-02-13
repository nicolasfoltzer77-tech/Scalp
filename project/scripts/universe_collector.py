#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import sqlite3
import yaml
import os

CONF_PATH = os.environ.get(
    "UNIVERSE_CONF",
    "/opt/scalp/project/conf/universe.conf.yaml"
)

# -------------------------------------------------
# utils
# -------------------------------------------------

def load_yaml(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def conn(path, ro=False):
    if ro:
        uri = f"file:{path}?mode=ro"
        return sqlite3.connect(uri, uri=True, timeout=5, isolation_level=None)
    return sqlite3.connect(path, timeout=5, isolation_level=None)

# -------------------------------------------------
# collectors
# -------------------------------------------------

def collect_volume_24h(ob_db):
    since = (int(time.time()) - 86400) * 1000
    db = conn(ob_db, ro=True)

    rows = db.execute("""
        SELECT instId, SUM(v)
        FROM ohlcv_1m
        WHERE ts >= ?
        GROUP BY instId
    """, (since,)).fetchall()

    db.close()
    return {inst: float(v or 0.0) for inst, v in rows}

def collect_ticks_24h(t_db):
    since = (int(time.time()) - 86400) * 1000
    db = conn(t_db, ro=True)

    rows = db.execute("""
        SELECT instId, COUNT(*)
        FROM ticks
        WHERE ts_ms >= ?
        GROUP BY instId
    """, (since,)).fetchall()

    db.close()
    return {inst: int(n or 0) for inst, n in rows}

# -------------------------------------------------
# upsert
# -------------------------------------------------

def upsert_universe(universe_db, volumes, ticks):
    db = conn(universe_db)
    db.execute("PRAGMA journal_mode=WAL;")
    db.execute("PRAGMA busy_timeout=5000;")

    now = int(time.time() * 1000)
    insts = set(volumes) | set(ticks)

    for instId in insts:
        db.execute("""
            INSERT INTO universe_coin (
                instId,
                status,
                enabled,

                volume_24h,
                ticks_24h,

                spread_avg,
                spread_p95,

                data_ok,
                status_exchange,

                ts_update
            )
            VALUES (
                ?, 'enabled', 0,
                ?, ?,
                NULL, NULL,
                1, 'listed',
                ?
            )
            ON CONFLICT(instId) DO UPDATE SET
                volume_24h = excluded.volume_24h,
                ticks_24h  = excluded.ticks_24h,
                ts_update  = excluded.ts_update
        """, (
            instId,
            volumes.get(instId, 0.0),
            ticks.get(instId, 0),
            now
        ))

    db.close()

# -------------------------------------------------
# main
# -------------------------------------------------

def main():
    cfg = load_yaml(CONF_PATH)

    vol = collect_volume_24h(cfg["sources"]["ob_db"])
    t24 = collect_ticks_24h(cfg["sources"]["t_db"])

    upsert_universe(cfg["paths"]["universe_db"], vol, t24)

    print(f"[OK] universe collected — {len(vol)} coins")

if __name__ == "__main__":
    main()

