#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import ccxt
import sqlite3
import time
import yaml
import logging
import sys

ROOT = "/opt/scalp/project"
CONF = f"{ROOT}/conf/universe.conf.yaml"
DB_UNIVERSE = f"{ROOT}/data/universe.db"

LOG = f"{ROOT}/logs/universe_tradable.log"
logging.basicConfig(
    filename=LOG,
    level=logging.INFO,
    format="%(asctime)s UNIVERSE_TRADABLE %(levelname)s %(message)s"
)
log = logging.getLogger("UNIVERSE_TRADABLE")

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
def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

# ------------------------------------------------------
# MAIN
# ------------------------------------------------------
def main():
    cfg = load_cfg()

    trad_cfg = cfg.get("tradable", {})
    VOL_MIN = float(trad_cfg.get("volume_24h_min", 0))
    BATCH   = int(trad_cfg.get("batch_size", 5))

    act_cfg = trad_cfg.get("activity_recent", {})
    ACT_ENABLED = bool(act_cfg.get("enabled", False))
    ACT_MAX_AGE = int(act_cfg.get("max_age_seconds", 120))

    ex = ccxt.bitget({
        "enableRateLimit": True,
        "timeout": 10000,
        "options": {"defaultType": "swap"}
    })

    db = conn(DB_UNIVERSE)

    insts = [r[0] for r in db.execute(
        "SELECT instId FROM v_universe_enabled"
    ).fetchall()]

    total = len(insts)
    if total == 0:
        print("[WARN] no universe input")
        return

    now = int(time.time() * 1000)
    kept = 0
    done = 0

    print(f"[INFO] universe_tradable_runner snapshot ({total} symbols)")
    sys.stdout.flush()

    for batch in chunks(insts, BATCH):
        try:
            tickers = ex.fetch_tickers(batch)
        except Exception as e:
            log.warning(f"batch fetch error: {e}")
            continue

        for inst in batch:
            t = tickers.get(inst)
            reason = None
            tradable = 0
            vol = 0.0

            if not t:
                reason = "no_ticker"
            else:
                vol = float(
                    t.get("quoteVolume")
                    or t.get("baseVolume", 0.0)
                    or 0.0
                )

                if vol < VOL_MIN:
                    reason = "low_volume"
                else:
                    tradable = 1

                # --------------------------------------
                # ACTIVITY RECENT (OPTIONAL GUARDFENCE)
                # --------------------------------------
                if tradable and ACT_ENABLED:
                    ts = t.get("timestamp")
                    if not ts:
                        tradable = 0
                        reason = "no_timestamp"
                    else:
                        age = int((now - ts) / 1000)
                        if age > ACT_MAX_AGE:
                            tradable = 0
                            reason = "inactive_recent"

            if tradable:
                kept += 1

            db.execute("""
                INSERT INTO universe_tradable
                    (instId, volume_24h, tradable, reason, ts_update)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(instId) DO UPDATE SET
                    volume_24h = excluded.volume_24h,
                    tradable   = excluded.tradable,
                    reason     = excluded.reason,
                    ts_update  = excluded.ts_update
            """, (inst, vol, tradable, reason, now))

            done += 1

        print(f"[PROGRESS] {done}/{total} tradable={kept}")
        sys.stdout.flush()

    db.close()
    print(f"[OK] universe_tradable_runner done → tradable={kept}/{total}")

if __name__ == "__main__":
    main()

