#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCALP — MARKET COLLECTOR (AUTHORITATIVE)

RÔLE :
- lire universe.db (v_universe_tradable)
- lire ticks (t.db)
- lire ohlcv (ob.db)
- snapshot REST ccxt
- calculer ticks_5s / spread / staleness
- ÉCRIRE market_latest (SEUL writer)
"""

import sqlite3
import time
import logging
import ccxt
from pathlib import Path
from collections import deque, defaultdict

# ============================================================
# PATHS
# ============================================================

ROOT = Path("/opt/scalp/project")

DB_U = ROOT / "data/universe.db"
DB_T = ROOT / "data/t.db"
DB_O = ROOT / "data/ob.db"
DB_M = ROOT / "data/market.db"

# ============================================================
# PARAMS
# ============================================================

LOOP_SLEEP   = 1.0
SNAPSHOT_TTL = 30.0
BATCH_SIZE   = 5

# ============================================================
# LOG
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s MARKET %(levelname)s %(message)s"
)
log = logging.getLogger("MARKET")

# ============================================================
# DB
# ============================================================

def conn(db):
    c = sqlite3.connect(str(db), timeout=10, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA synchronous=NORMAL;")
    c.execute("PRAGMA busy_timeout=5000;")
    return c

# ============================================================
# UNIVERSE
# ============================================================

def load_universe():
    cu = conn(DB_U)
    xs = [r[0] for r in cu.execute(
        "SELECT instId FROM v_universe_tradable"
    ).fetchall()]
    cu.close()
    log.info("Universe loaded: %d symbols", len(xs))
    return xs

# ============================================================
# CCXT SNAPSHOT
# ============================================================

EX = ccxt.bitget({"options": {"defaultType": "swap"}})

snapshot_cache = {}
snapshot_ts = 0.0

def refresh_snapshots(insts):
    global snapshot_cache, snapshot_ts

    now = time.time()
    if now - snapshot_ts < SNAPSHOT_TTL:
        return

    snapshot_cache.clear()
    log.info("Refreshing snapshots (%d symbols)", len(insts))

    for i in range(0, len(insts), BATCH_SIZE):
        batch = insts[i:i + BATCH_SIZE]
        syms = [x.replace("/", "") for x in batch]

        try:
            res = EX.fetch_tickers(syms)
        except Exception as e:
            log.error("Snapshot batch FAIL: %s", e)
            continue

        for k, t in res.items():
            if not t:
                continue

            inst = k.split(":")[0]
            if inst not in insts:
                continue

            snapshot_cache[inst] = {
                "last": float(t.get("last") or 0.0),
                "bid":  float(t.get("bid") or 0.0),
                "ask":  float(t.get("ask") or 0.0),
                "volume_24h": float(t.get("quoteVolume") or 0.0),
            }

    snapshot_ts = now
    log.info("Snapshot refresh done (%d cached)", len(snapshot_cache))

# ============================================================
# ATR 1m
# ============================================================

def atr_1m(inst, period=14):
    co = conn(DB_O)
    rows = co.execute("""
        SELECT h,l,c
        FROM ohlcv_1m
        WHERE instId=?
        ORDER BY ts DESC
        LIMIT ?
    """, (inst, period + 1)).fetchall()
    co.close()

    if len(rows) < period + 1:
        return None

    trs = []
    for i in range(1, period + 1):
        h, l, c = rows[i]
        pc = rows[i - 1][2]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))

    return sum(trs) / period

# ============================================================
# TICKS BUFFER
# ============================================================

tick_buf = defaultdict(lambda: deque(maxlen=500))

def update_ticks():
    ct = conn(DB_T)
    rows = ct.execute("""
        SELECT instId, lastPr, ts_ms
        FROM ticks
        WHERE ts_ms > ?
    """, (int(time.time() * 1000) - 5000,)).fetchall()
    ct.close()

    for r in rows:
        tick_buf[r["instId"]].append((r["ts_ms"], r["lastPr"]))

# ============================================================
# MAIN LOOP
# ============================================================

def main():
    log.info("MARKET START")

    universe = load_universe()
    cm = conn(DB_M)

    while True:
        try:
            now_ms = int(time.time() * 1000)

            update_ticks()
            refresh_snapshots(universe)

            for inst in universe:
                buf  = tick_buf.get(inst)
                snap = snapshot_cache.get(inst)

                if not buf or not snap or snap["last"] <= 0:
                    continue

                ticks_5s = sum(1 for ts, _ in buf if ts > now_ms - 5000)
                last_ts, _ = buf[-1]
                staleness = now_ms - last_ts

                spread = snap["ask"] - snap["bid"]
                spread_bps = (spread / snap["last"] * 10000) if snap["last"] else 0.0

                # ===============================
                # 🔑 AUTHORITATIVE WRITE
                # ===============================
                cm.execute("""
                    INSERT INTO market_latest (
                        instId,
                        ticks_5s,
                        spread_bps,
                        staleness_ms,
                        ts_update
                    ) VALUES (?,?,?,?,?)
                    ON CONFLICT(instId) DO UPDATE SET
                        ticks_5s     = excluded.ticks_5s,
                        spread_bps   = excluded.spread_bps,
                        staleness_ms = excluded.staleness_ms,
                        ts_update    = excluded.ts_update
                """, (
                    inst,
                    ticks_5s,
                    spread_bps,
                    staleness,
                    now_ms
                ))

            time.sleep(LOOP_SLEEP)

        except Exception:
            log.exception("MARKET LOOP ERROR")
            time.sleep(2)

if __name__ == "__main__":
    main()

