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

LOG = f"{ROOT}/logs/universe_probe.log"
logging.basicConfig(
    filename=LOG,
    level=logging.INFO,
    format="%(asctime)s UNIVERSE_PROBE %(levelname)s %(message)s"
)
log = logging.getLogger("UNIVERSE_PROBE")

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
# CONFIG
# ------------------------------------------------------
def load_cfg():
    with open(CONF, "r") as f:
        return yaml.safe_load(f)

# ------------------------------------------------------
# CANONICAL instId : BASE/USDT
# ------------------------------------------------------
def canon_inst_usdt(symbol: str):
    if not symbol:
        return None
    s = symbol.upper().replace("_", "").replace("-", "").replace("/", "")
    if not s.endswith("USDT"):
        return None
    base = s[:-4]
    if not base:
        return None
    return f"{base}/USDT"

# ------------------------------------------------------
# PROBE OHLCV — MARKET EXISTENCE (GLOBAL)
# ------------------------------------------------------
def probe_ohlcv(exchange, instId, cfg):
    p = cfg["universe_probes"]["ohlcv"]
    tf = p["timeframe"]

    try:
        candles = exchange.fetch_ohlcv(
            instId,
            timeframe=tf,
            since=None,
            limit=p["max_lookback_bars"]
        )
    except Exception as e:
        log.debug(f"{instId} fetch error: {e}")
        return (0, 0, None, None)

    if not candles:
        return (0, 0, None, None)

    n = len(candles)
    last_ts = candles[-1][0]
    now_ms = int(time.time() * 1000)
    staleness = int((now_ms - last_ts) / 1000)

    ok = (
        n >= p["min_candles"]
        and staleness <= p["max_staleness_seconds"]
    )

    return (1 if ok else 0, n, last_ts, staleness)

# ------------------------------------------------------
# MAIN
# ------------------------------------------------------
def main():
    cfg = load_cfg()
    if not cfg.get("universe_probes", {}).get("enabled", False):
        log.info("Universe probes disabled")
        return

    # -------- source UNIVERSE : universe_seed (EXHAUSTIF)
    db = conn(DB_UNIVERSE)
    seeds = [r[0] for r in db.execute(
        "SELECT instId FROM universe_seed ORDER BY instId"
    ).fetchall()]

    # -------- exchange (ccxt, read-only)
    ex = getattr(ccxt, cfg["exchange"]["ccxt_id"])({
        "options": cfg["exchange"]["options"]
    })

    now = int(time.time() * 1000)

    ok_cnt = 0

    for seed in seeds:
        inst = canon_inst_usdt(seed)
        if not inst:
            continue

        ohlcv_ok, candle_count, last_ts, staleness = probe_ohlcv(ex, inst, cfg)

        db.execute("""
            INSERT INTO universe_coin (
                instId,
                status,
                enabled,
                data_ok,
                status_exchange,
                ts_update
            )
            VALUES (?, 'enabled', 0, ?, 'listed', ?)
            ON CONFLICT(instId) DO UPDATE SET
                data_ok   = excluded.data_ok,
                ts_update = excluded.ts_update
        """, (inst, ohlcv_ok, now))

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
            VALUES (?, ?, ?, ?, ?, NULL, ?)
            ON CONFLICT(instId) DO UPDATE SET
                ohlcv_ok       = excluded.ohlcv_ok,
                candle_count  = excluded.candle_count,
                last_ts       = excluded.last_ts,
                staleness_sec = excluded.staleness_sec,
                ts_update     = excluded.ts_update
        """, (
            inst,
            ohlcv_ok,
            candle_count,
            last_ts,
            staleness,
            now
        ))

        if ohlcv_ok:
            ok_cnt += 1

    db.close()
    print(f"[OK] universe_probe_ccxt done — data_ok={ok_cnt}/{len(seeds)}")

if __name__ == "__main__":
    main()

