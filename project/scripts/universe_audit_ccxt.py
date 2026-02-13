#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import ccxt
import sqlite3
import time
import yaml
import logging

ROOT = "/opt/scalp/project"
CONF = f"{ROOT}/conf/universe.conf.yaml"
DB_UNIVERSE = f"{ROOT}/data/universe.db"
DB_U = f"{ROOT}/data/u.db"

LOG = f"{ROOT}/logs/universe_audit.log"
logging.basicConfig(
    filename=LOG,
    level=logging.INFO,
    format="%(asctime)s UNIVERSE_AUDIT %(levelname)s %(message)s"
)
log = logging.getLogger("UNIVERSE_AUDIT")

# --------------------------------------------------
def conn(path):
    c = sqlite3.connect(path, timeout=30, isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA synchronous=NORMAL;")
    c.execute("PRAGMA busy_timeout=5000;")
    return c

def load_cfg():
    with open(CONF, "r") as f:
        return yaml.safe_load(f)

def canon_inst_usdt(instId):
    s = instId.upper().replace("_", "").replace("-", "").replace("/", "")
    if not s.endswith("USDT"):
        return None
    return f"{s[:-4]}/USDT"

# --------------------------------------------------
def main():
    cfg = load_cfg()
    p = cfg["universe_probes"]["ohlcv"]

    # --- candidates universe (structurels)
    cu = conn(DB_U)
    raw = [r[0] for r in cu.execute("SELECT instId FROM v_universe_tradable;").fetchall()]
    cu.close()

    # --- exchange ccxt (read-only)
    ex = getattr(ccxt, cfg["exchange"]["ccxt_id"])({
        "options": cfg["exchange"]["options"]
    })

    db = conn(DB_UNIVERSE)
    now = int(time.time() * 1000)

    for r in raw:
        inst = canon_inst_usdt(r)
        if not inst:
            continue

        try:
            candles = ex.fetch_ohlcv(
                inst,
                timeframe=p["timeframe"],
                limit=p["max_lookback_bars"]
            )

            n = len(candles)
            if n == 0:
                raise Exception("no_candles")

            last_ts = candles[-1][0]
            staleness = int((now - last_ts) / 1000)

            ok = (
                n >= p["min_candles"]
                and staleness <= p["max_staleness_seconds"]
            )

            err = None if ok else "ohlcv_invalid"

        except Exception as e:
            ok = 0
            n = 0
            last_ts = None
            staleness = None
            err = str(e)

        db.execute("""
            INSERT INTO universe_probe_audit (
                instId,
                ohlcv_ok,
                candle_count,
                last_ts,
                staleness_sec,
                error,
                ts_update
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(instId) DO UPDATE SET
                ohlcv_ok       = excluded.ohlcv_ok,
                candle_count  = excluded.candle_count,
                last_ts       = excluded.last_ts,
                staleness_sec = excluded.staleness_sec,
                error         = excluded.error,
                ts_update     = excluded.ts_update
        """, (
            inst,
            1 if ok else 0,
            n,
            last_ts,
            staleness,
            err,
            now
        ))

        log.info(f"{inst} ok={ok} n={n} stale={staleness} err={err}")

    db.close()
    log.info("UNIVERSE AUDIT DONE")

if __name__ == "__main__":
    main()

