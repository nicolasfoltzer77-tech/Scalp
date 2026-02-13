#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import ccxt
import sqlite3
import time
import logging

ROOT = "/opt/scalp/project"
DB_UNIVERSE = f"{ROOT}/data/universe.db"

LOG = f"{ROOT}/logs/universe_seed.log"
logging.basicConfig(
    filename=LOG,
    level=logging.INFO,
    format="%(asctime)s UNIVERSE_SEED %(levelname)s %(message)s"
)
log = logging.getLogger("UNIVERSE_SEED")

# ------------------------------------------------------
# DB
# ------------------------------------------------------
def conn(path):
    c = sqlite3.connect(path, timeout=30, isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA synchronous=NORMAL;")
    c.execute("PRAGMA busy_timeout=5000;")
    return c

# ------------------------------------------------------
# MAIN
# ------------------------------------------------------
def main():
    log.info("START universe_seed_ccxt")

    ex = ccxt.bitget({
        "options": {"defaultType": "swap"}
    })

    markets = ex.load_markets()
    now = int(time.time() * 1000)

    db = conn(DB_UNIVERSE)

    n_total = 0
    n_kept = 0

    for m in markets.values():
        n_total += 1

        # --- STRUCTURAL FILTERS ONLY
        if not m.get("swap"):
            continue
        if m.get("quote") != "USDT":
            continue
        if not m.get("active", True):
            continue

        base = m.get("base")
        if not base:
            continue

        inst = f"{base}/USDT"

        db.execute("""
            INSERT INTO universe_seed (
                instId,
                source,
                ts_update
            )
            VALUES (?, 'ccxt', ?)
            ON CONFLICT(instId) DO UPDATE SET
                ts_update = excluded.ts_update
        """, (inst, now))

        n_kept += 1

    db.close()

    log.info(f"END universe_seed_ccxt total={n_total} kept={n_kept}")
    print(f"[OK] universe_seed_ccxt → {n_kept} swap USDT markets")

if __name__ == "__main__":
    main()

