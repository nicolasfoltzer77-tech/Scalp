#!/usr/bin/env python3
import time
import sqlite3
import ccxt
from datetime import datetime

DB_U  = "/opt/scalp/project/data/universe.db"
DB_OA = "/opt/scalp/project/data/oa.db"

TF_MS = {
    "5m":  5  * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "30m": 30 * 60 * 1000
}

TABLE = {
    "5m":  "ohlcv_5m",
    "15m": "ohlcv_15m",
    "30m": "ohlcv_30m"
}

###############################################################################
# DB helpers
###############################################################################
def load_universe():
    c = sqlite3.connect(DB_U)
    rows = c.execute("SELECT instId FROM v_universe_tradable ORDER BY instId").fetchall()
    c.close()
    return [r[0] for r in rows]

def conn_oa():
    c = sqlite3.connect(DB_OA, timeout=10)
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA synchronous=NORMAL;")
    return c

###############################################################################
# CCXT fetch
###############################################################################
EX = ccxt.bitget({"options":{"defaultType":"swap"}})

def fetch_missing(instId, tf, since_ts):
    market = instId.replace("/", "")
    try:
        return EX.fetch_ohlcv(market, timeframe=tf, since=since_ts, limit=5)
    except Exception as e:
        print(f"[OA] CCXT error {instId} {tf}: {e}")
        return []

###############################################################################
# Insert rows
###############################################################################
def insert_row(con, tf, instId, ts, o, h, l, c, v):
    con.execute(
        f"INSERT OR REPLACE INTO {TABLE[tf]}(instId, ts, open, high, low, close, volume)"
        f" VALUES (?,?,?,?,?,?,?)",
        (instId, ts, o, h, l, c, v)
    )

###############################################################################
# Main OA logic
###############################################################################
def sync_inst(con, instId):
    now = int(time.time() * 1000)

    for tf, tf_ms in TF_MS.items():

        row = con.execute(
            f"SELECT ts FROM {TABLE[tf]} WHERE instId=? ORDER BY ts DESC LIMIT 1",
            (instId,)
        ).fetchone()

        last_ts = row[0] if row else (now - tf_ms * 10)

        # Fetch only the missing window
        ohlcv = fetch_missing(instId, tf, last_ts)
        if not ohlcv:
            continue

        for ts, o, h, l, c, v in ohlcv:

            # Normaliser timestamp (sécurité)
            if ts < 10**11:   # seconde → millisecondes
                ts = ts * 1000

            # Validation strict millisecondes
            if ts > now + 3600 * 1000:
                print(f"[OA] WARNING {instId} {tf} future-ts={ts}")
                continue

            if ts > last_ts:
                insert_row(con, tf, instId, ts, o, h, l, c, v)
                print(f"[OA] {instId} {tf} synced ts={ts}")

###############################################################################
# Entrypoint
###############################################################################
def main():
    t0 = time.time()

    universe = load_universe()
    con = conn_oa()

    for instId in universe:
        try:
            sync_inst(con, instId)
        except Exception as e:
            print(f"[OA] ERROR {instId}: {e}")

    con.commit()
    con.close()

    print(f"[OA] Sync OK in {time.time() - t0:.3f}s")

if __name__ == "__main__":
    main()

