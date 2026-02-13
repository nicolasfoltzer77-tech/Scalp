#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import sqlite3
import ccxt

DB = "/opt/scalp/project/data/universe.db"

def conn(path: str):
    c = sqlite3.connect(path, timeout=30, isolation_level=None)
    c.execute("PRAGMA busy_timeout=5000;")
    return c

def get_next_seed(db, inst: str):
    row = db.execute(
        "SELECT instId FROM universe_seed WHERE instId > ? ORDER BY instId LIMIT 1",
        (inst,)
    ).fetchone()
    return row[0] if row else None

def fetch_probe(ex, inst: str, tf="1m", limit=50):
    now_ms = int(time.time() * 1000)
    try:
        candles = ex.fetch_ohlcv(inst, timeframe=tf, since=None, limit=limit)
        n = len(candles) if candles else 0
        last_ts = candles[-1][0] if n > 0 else None
        stale = int((now_ms - last_ts) / 1000) if last_ts else None
        return {
            "inst": inst,
            "ok_call": True,
            "n": n,
            "last_ts": last_ts,
            "staleness_sec": stale,
            "error": None,
        }
    except Exception as e:
        return {
            "inst": inst,
            "ok_call": False,
            "n": 0,
            "last_ts": None,
            "staleness_sec": None,
            "error": str(e),
        }

def fmt_ts(ts_ms):
    if ts_ms is None:
        return "NULL"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts_ms / 1000))

def main():
    db = conn(DB)

    inst_ok = "XTZ/USDT"
    inst_next = get_next_seed(db, inst_ok)

    if not inst_next:
        print("[ERR] No next seed found after XTZ/USDT")
        return

    print(f"[INFO] inst_ok   = {inst_ok}")
    print(f"[INFO] inst_next = {inst_next}")
    print()

    # same exchange settings as your OA stack
    ex = ccxt.bitget({"options": {"defaultType": "swap"}})

    r1 = fetch_probe(ex, inst_ok, tf="1m", limit=50)
    r2 = fetch_probe(ex, inst_next, tf="1m", limit=50)

    for r in (r1, r2):
        print(f"== {r['inst']} ==")
        print(f"ok_call        : {r['ok_call']}")
        print(f"candle_count   : {r['n']}")
        print(f"last_ts_ms     : {r['last_ts']}")
        print(f"last_ts_human  : {fmt_ts(r['last_ts'])}")
        print(f"staleness_sec  : {r['staleness_sec']}")
        print(f"error          : {r['error']}")
        print()

if __name__ == "__main__":
    main()

