#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import ccxt
import logging
import time

ROOT = "/opt/scalp/project"
DB_OB = f"{ROOT}/data/ob.db"
DB_U  = f"{ROOT}/data/universe.db"
LOG   = f"{ROOT}/logs/ob_collect.log"

logging.basicConfig(
    filename=LOG,
    level=logging.INFO,
    format="%(asctime)s OB_COLLECT %(levelname)s %(message)s"
)
log = logging.getLogger("OB_COLLECT")

# ==========================================================
# DB
# ==========================================================
def conn(path):
    c = sqlite3.connect(path, timeout=10, isolation_level=None)
    c.execute("PRAGMA busy_timeout=5000;")
    return c

def load_universe():
    cu = conn(DB_U)
    xs = [r[0] for r in cu.execute("SELECT instId FROM v_universe_tradable;")]
    cu.close()
    return xs

def last_ts(conn, table, inst):
    try:
        r = conn.execute(
            f"SELECT ts FROM {table} WHERE instId=? ORDER BY ts DESC LIMIT 1",
            (inst,)
        ).fetchone()
        return r[0] if r else 0
    except:
        return 0

# ==========================================================
# FETCH CCXT
# ==========================================================
EX = ccxt.bitget()

def fetch_tf(inst, tf, limit=200):
    try:
        symbol = inst.replace("/", "")
        rows = EX.fetch_ohlcv(symbol, timeframe=tf, limit=limit)
        return [(ts, o, h, l, c, v) for ts,o,h,l,c,v in rows]
    except Exception as e:
        log.error(f"{inst} {tf} FAIL {e}")
        return []

# ==========================================================
# AGGREGATION 3m
# ==========================================================
def aggregate_3m(conn):
    conn.execute("""
    INSERT OR REPLACE INTO ohlcv_3m(instId, ts, o, h, l, c, v)
    SELECT instId,
           (ts/180000)*180000 AS ts,
           FIRST_VALUE(o) OVER w,
           MAX(h)          OVER w,
           MIN(l)          OVER w,
           LAST_VALUE(c)   OVER w,
           SUM(v)          OVER w
    FROM ohlcv_1m
    WINDOW w AS (
        PARTITION BY instId, (ts/180000)
        ORDER BY ts
        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
    );
    """)

# ==========================================================
# PURGE OB
# ==========================================================
PURGE_1M_HIGH = 1500
PURGE_1M_LOW  = 450

PURGE_HIGH = 500
PURGE_LOW  = 150

def purge_ob(conn, tf, inst):
    table = f"ohlcv_{tf}"

    r = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE instId=?", (inst,)).fetchone()
    if not r:
        return
    count = r[0]

    if tf == "1m":
        H = PURGE_1M_HIGH
        L = PURGE_1M_LOW
    else:
        H = PURGE_HIGH
        L = PURGE_LOW

    if count <= H:
        return

    rows = conn.execute(
        f"SELECT ts FROM {table} WHERE instId=? ORDER BY ts DESC LIMIT ? OFFSET ?",
        (inst, H, L)
    ).fetchall()

    if not rows:
        return

    cutoff = rows[-1][0]

    conn.execute(
        f"DELETE FROM {table} WHERE instId=? AND ts < ?",
        (inst, cutoff)
    )

    log.info(f"{inst} PURGE {table}: kept {H}, deleted older")


# ==========================================================
# MAIN
# ==========================================================
def main():
    log.info("OB START")

    co = conn(DB_OB)
    coins = load_universe()

    for inst in coins:

        # -------------------------------
        # 1m incremental
        # -------------------------------
        last = last_ts(co, "ohlcv_1m", inst)
        rows = fetch_tf(inst, "1m")
        new_1m = [r for r in rows if r[0] > last]

        if new_1m:
            co.executemany(
                "INSERT INTO ohlcv_1m VALUES (?,?,?,?,?,?,?)",
                [(inst,) + r for r in new_1m]
            )

        log.info(f"{inst} new1m={len(new_1m)}")

        # purge 1m
        purge_ob(co, "1m", inst)

        # -------------------------------
        # 5m incremental
        # -------------------------------
        last = last_ts(co, "ohlcv_5m", inst)
        rows = fetch_tf(inst, "5m")
        new_5m = [r for r in rows if r[0] > last]

        if new_5m:
            co.executemany(
                "INSERT INTO ohlcv_5m VALUES (?,?,?,?,?,?,?)",
                [(inst,) + r for r in new_5m]
            )

        log.info(f"{inst} new5m={len(new_5m)}")

        # purge 5m
        purge_ob(co, "5m", inst)

    # -------------------------------
    # 3m aggregation
    # -------------------------------
    try:
        aggregate_3m(co)
        log.info("3m aggregation OK")
    except Exception as e:
        log.error(f"3m aggregation FAIL {e}")

    log.info("OB DONE")


if __name__ == "__main__":
    main()

