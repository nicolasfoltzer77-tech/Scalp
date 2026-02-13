#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import yaml
import sqlite3
import requests
import os
import sys

CONF_PATH = os.environ.get(
    "UNIVERSE_CONF",
    "/opt/scalp/project/conf/universe.conf.yaml"
)

# ------------------------------------------------------------
# utils
# ------------------------------------------------------------

def load_yaml(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def db_connect(path):
    db = sqlite3.connect(path, timeout=5, isolation_level=None)
    db.execute("PRAGMA journal_mode=WAL;")
    db.execute("PRAGMA busy_timeout=5000;")
    return db

def http_get(url, params, timeout, retries):
    for _ in range(retries + 1):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        time.sleep(0.2)
    return None

# ------------------------------------------------------------
# probes
# ------------------------------------------------------------

def probe_meta(cfg):
    url = cfg["exchange"]["rest_base_url"] + cfg["probes"]["meta"]["endpoint"]
    js = http_get(
        url,
        params={},
        timeout=cfg["exchange"]["timeouts"]["read_seconds"],
        retries=cfg["exchange"]["timeouts"]["max_retries"],
    )
    if not js or "data" not in js:
        return {}

    out = {}
    for row in js["data"]:
        inst = row.get("symbol")
        if not inst:
            continue

        ok = (
            row.get("status") == cfg["probes"]["meta"]["require_status"]
            and row.get("tradeEnable", True)
        )

        out[inst] = {
            "status_exchange": row.get("status"),
            "meta_ok": 1 if ok else 0,
        }
    return out

def probe_ohlcv(cfg, instId):
    p = cfg["probes"]["ohlcv"]
    url = cfg["exchange"]["rest_base_url"] + p["endpoint"]

    params = {
        "symbol": instId,
        "granularity": p["granularity"],
        "limit": p["min_candles"],
    }

    js = http_get(
        url,
        params=params,
        timeout=cfg["exchange"]["timeouts"]["read_seconds"],
        retries=cfg["exchange"]["timeouts"]["max_retries"],
    )

    if not js or "data" not in js or len(js["data"]) < p["min_candles"]:
        return 0

    ts = [int(c[0]) for c in js["data"]]
    ts.sort()

    if ts[-1] < int(time.time() * 1000) - p["max_staleness_ms"]:
        return 0

    for i in range(1, len(ts)):
        if ts[i] - ts[i - 1] > p["max_gap_ms"]:
            return 0

    return 1

def probe_trades(cfg, instId):
    p = cfg["probes"]["trades"]
    url = cfg["exchange"]["rest_base_url"] + p["endpoint"]

    params = {
        "symbol": instId,
        "limit": p["min_trades"],
    }

    js = http_get(
        url,
        params=params,
        timeout=cfg["exchange"]["timeouts"]["read_seconds"],
        retries=cfg["exchange"]["timeouts"]["max_retries"],
    )

    if not js or "data" not in js:
        return 0

    now_ms = int(time.time() * 1000)
    trades = js["data"]

    if len(trades) < p["min_trades"]:
        return 0

    notional = 0.0
    recent = 0

    for t in trades:
        ts = int(t.get("ts", 0))
        if ts >= now_ms - p["lookback_seconds"] * 1000:
            recent += 1
            notional += float(t.get("quoteVol", 0.0))

    if recent < p["min_trades"]:
        return 0
    if notional < p["min_notional"]:
        return 0

    return 1

# ------------------------------------------------------------
# main
# ------------------------------------------------------------

def main():
    cfg = load_yaml(CONF_PATH)

    universe_db = cfg["paths"]["universe_db"]
    probes_cfg  = cfg["probes"]

    db = db_connect(universe_db)

    meta = probe_meta(cfg)
    now = int(time.time() * 1000)

    for instId, m in meta.items():
        ohlcv_ok = 1
        trades_ok = 1

        if probes_cfg["ohlcv"]["enabled"]:
            ohlcv_ok = probe_ohlcv(cfg, instId)

        if probes_cfg["trades"]["enabled"]:
            trades_ok = probe_trades(cfg, instId)

        data_ok = 1 if (m["meta_ok"] and ohlcv_ok and trades_ok) else 0

        db.execute("""
            INSERT INTO universe_coin (
                instId,
                status,
                enabled,
                data_ok,
                status_exchange,
                ts_update
            )
            VALUES (?, 'enabled', 0, ?, ?, ?)
            ON CONFLICT(instId) DO UPDATE SET
                data_ok = excluded.data_ok,
                status_exchange = excluded.status_exchange,
                ts_update = excluded.ts_update
        """, (
            instId,
            data_ok,
            m["status_exchange"],
            now
        ))

    db.close()

    print(f"[OK] universe probes applied ({len(meta)} symbols)")

if __name__ == "__main__":
    main()

