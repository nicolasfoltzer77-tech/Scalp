#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import time
import logging
import traceback
import ccxt

ROOT = "/opt/scalp/project"
DB_U  = f"{ROOT}/data/universe.db"
DB_OA = f"{ROOT}/data/oa.db"
LOG   = f"{ROOT}/logs/oa_ohlcv.log"

logging.basicConfig(
    filename=LOG,
    level=logging.INFO,
    format="%(asctime)s OA %(levelname)s %(message)s"
)
log = logging.getLogger("OA")

# ============================================================
# DB
# ============================================================
def conn(path):
    c = sqlite3.connect(path, timeout=5, isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA synchronous=NORMAL;")
    c.execute("PRAGMA busy_timeout=3000;")
    return c

# ============================================================
# EXCHANGE
# ============================================================
exchange = ccxt.bitget({
    "options": {"defaultType": "swap"},
})

# Map TF → minutes
TF_MAP = {
    "5m": 5,
    "15m": 15,
    "30m": 30,
}

# ============================================================
# LOAD UNIVERSE
# ============================================================
def load_universe():
    cu = conn(DB_U)
    rows = cu.execute("SELECT instId FROM v_universe_tradable ORDER BY instId").fetchall()
    return [r[0] for r in rows]

# ============================================================
# FETCH OHLCV FROM EXCHANGE
# ============================================================
def fetch_ohlcv(instId, tf):
    """
    Retourne une liste de bougies CCXT :
      [ts_ms, open, high, low, close, volume]
    """
    try:
        candles = exchange.fetch_ohlcv(instId.replace("/",""), timeframe=tf)
        if not candles:
            return []
        return candles
    except Exception as e:
        log.error(f"{instId} {tf} fetch error: {e}")
        return []

# ============================================================
# SAVE OHLCV → oa.db
# ============================================================
def save_candles(instId, tf, candles):
    """
    candles = liste CCXT format standard
    """
    if not candles:
        return 0

    table = f"ohlcv_{tf}"
    c = conn(DB_OA)

    cnt = 0
    for row in candles:
        ts = int(row[0])  # timestamp en ms
        o = float(row[1])
        h = float(row[2])
        l = float(row[3])
        pc = float(row[4])
        v = float(row[5])

        # IMPÉRATIF : empêcher ts NULL
        if ts <= 0:
            continue

        try:
            c.execute(f"""
                INSERT OR REPLACE INTO {table}(
                    instId, ts, open, high, low, close, volume
                ) VALUES (?,?,?,?,?,?,?)
            """, (instId, ts, o, h, l, pc, v))
            cnt += 1
        except Exception as e:
            log.error(f"{instId} {tf} insert error: {e}")

    return cnt

# ============================================================
# PURGE : garder les 150 dernières bougies
# ============================================================
def purge_tf(tf):
    table = f"ohlcv_{tf}"
    c = conn(DB_OA)

    insts = c.execute(f"SELECT DISTINCT instId FROM {table}").fetchall()
    for (instId,) in insts:
        try:
            # Récupère tous les ts triés descendant
            rows = c.execute(f"""
                SELECT ts FROM {table}
                WHERE instId=?
                ORDER BY ts DESC
                LIMIT 150
            """, (instId,)).fetchall()

            if len(rows) < 150:
                continue

            oldest_keep = rows[-1][0]  # ts du 150ème

            c.execute(f"""
                DELETE FROM {table}
                WHERE instId=? AND ts < ?
            """, (instId, oldest_keep))

        except Exception as e:
            log.error(f"purge {instId} {tf} error: {e}")

# ============================================================
# MAIN
# ============================================================
def main():
    log.info("OA START")

    insts = load_universe()

    for instId in insts:
        for tf in ("5m", "15m", "30m"):
            candles = fetch_ohlcv(instId, tf)
            n = save_candles(instId, tf, candles)
            log.info(f"{instId} {tf} → {n} candles")

    # PURGE
    for tf in ("5m", "15m", "30m"):
        purge_tf(tf)

    log.info("OA END")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.error(f"FATAL: {e}")
        log.error(traceback.format_exc())

