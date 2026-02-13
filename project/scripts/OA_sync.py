#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import ccxt, sqlite3, time, logging, traceback

ROOT = "/opt/scalp/project"
DB_OA = f"{ROOT}/data/oa.db"
DB_U  = f"{ROOT}/data/universe.db"

LOG = f"{ROOT}/logs/oa.log"

logging.basicConfig(
    filename=LOG,
    level=logging.INFO,
    format="%(asctime)s OA %(levelname)s %(message)s"
)
log = logging.getLogger("OA")

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
# PURGE : only if >500 --> keep 150
# ------------------------------------------------------
def purge_if_needed(c, table):
    n = c.execute(f"SELECT COUNT(*) FROM {table};").fetchone()[0]
    if n > 500:
        c.execute(f"""
            DELETE FROM {table}
            WHERE ts NOT IN (
                SELECT ts FROM {table}
                ORDER BY ts DESC
                LIMIT 150
            );
        """)
        log.info(f"Purged {table}: {n} -> 150")

# ------------------------------------------------------
# FETCH INCREMENTAL
# ------------------------------------------------------
def fetch_incremental(exchange, instId, tf, table):
    c = conn(DB_OA)

    # get last ts
    row = c.execute(f"SELECT MAX(ts) FROM {table} WHERE instId=?;", (instId,)).fetchone()
    last_ts = row[0] if row and row[0] else None

    ms_tf = {
        "5m":  5 * 60 * 1000,
        "15m": 15 * 60 * 1000,
        "30m": 30 * 60 * 1000
    }[tf]

    since = last_ts + ms_tf if last_ts else int(time.time()*1000) - (150 * ms_tf)

    try:
        ohlcv = exchange.fetch_ohlcv(instId, timeframe=tf, since=since, limit=500)
    except Exception as e:
        log.error(f"{instId} fetch error {tf}: {e}")
        return 0

    n_inserted = 0
    for ts, o, h, l, cl, v in ohlcv:
        try:
            c.execute(f"""
                INSERT OR IGNORE INTO {table}(instId, ts, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (instId, ts, o, h, l, cl, v))
            n_inserted += 1
        except Exception as e:
            log.error(f"Insert error {instId} {tf} {ts}: {e}")

    purge_if_needed(c, table)
    return n_inserted

# ------------------------------------------------------
# MAIN
# ------------------------------------------------------
def main():
    log.info("START OA_SYNC")

    cU = conn(DB_U)
    insts = [r[0] for r in cU.execute("SELECT instId FROM v_universe_tradable;").fetchall()]

    exchange = ccxt.bitget({"options": {"defaultType": "swap"}})

    for inst in insts:
        for tf, table in [
            ("5m",  "ohlcv_5m"),
            ("15m", "ohlcv_15m"),
            ("30m", "ohlcv_30m")
        ]:
            n = fetch_incremental(exchange, inst, tf, table)
            log.info(f"{inst} {tf} → {n} new")

    log.info("END OA_SYNC")

if __name__ == "__main__":
    main()

