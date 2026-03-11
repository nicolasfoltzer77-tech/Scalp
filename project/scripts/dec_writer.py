#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import logging
import sys
import sqlite3
import hashlib
from pathlib import Path

from dec_atr import refresh_snap_atr
from dec_range import refresh_snap_range
from dec_range_ext import refresh_snap_range_ext
from dec_signal import refresh_signal_history
from dec_cluster import refresh_cluster_history


ROOT = Path("/opt/scalp/project")

DB_TICKS = ROOT / "data/t.db"
DB_DEC   = ROOT / "data/dec.db"

LOG_PATH = ROOT / "logs/dec_writer.log"

BASE_SLEEP = 0.15
HEARTBEAT_MS = 10000


# --------------------------------------------------
# Logging
# --------------------------------------------------

logger = logging.getLogger("DEC")
logger.setLevel(logging.INFO)

fmt = logging.Formatter("%(asctime)s DEC %(levelname)s %(message)s")

fh = logging.FileHandler(LOG_PATH)
fh.setFormatter(fmt)
logger.addHandler(fh)

sh = logging.StreamHandler(sys.stdout)
sh.setFormatter(fmt)
logger.addHandler(sh)

log = logger


# --------------------------------------------------
# DB connections
# --------------------------------------------------

def conn_ticks():
    c = sqlite3.connect(str(DB_TICKS), timeout=5)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    return c


def conn_dec():
    c = sqlite3.connect(str(DB_DEC), timeout=5)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c


# --------------------------------------------------
# Latest tick
# --------------------------------------------------

def latest_tick_ts():

    try:

        with conn_ticks() as c:

            r = c.execute(
                "SELECT MAX(ts_ms) AS ts FROM ticks"
            ).fetchone()

        return int(r["ts"] or 0)

    except Exception:

        log.exception("[TICK_READ_ERROR]")
        return 0


# --------------------------------------------------
# Tick history
# --------------------------------------------------

def update_tick_history(conn):

    conn.execute("""
    INSERT INTO snap_ticks (instId,lastPr,ts)
    SELECT instId,lastPr,strftime('%s','now')
    FROM ticks_live
    """)

    conn.execute("""
    DELETE FROM snap_ticks
    WHERE ts < (
        SELECT ts
        FROM snap_ticks s2
        WHERE s2.instId = snap_ticks.instId
        ORDER BY ts DESC
        LIMIT 1 OFFSET 9
    )
    """)

    conn.commit()


# --------------------------------------------------
# Orderflow refresh
# --------------------------------------------------

def refresh_snap_orderflow(conn):

    conn.execute("""
    INSERT OR REPLACE INTO snap_orderflow
    SELECT

    r.instId,

    (r.volatility * 100) +
    COALESCE((t.lastPr - t2.lastPr) * 10,0),

    (r.compression * 100) +
    COALESCE((t2.lastPr - t.lastPr) * 10,0),

    (r.volatility - r.compression),

    ROUND(
        1 + (r.volatility - r.compression),
        3
    ),

    strftime('%s','now')

    FROM snap_range_ext r
    LEFT JOIN ticks_live t USING(instId)
    LEFT JOIN (
        SELECT instId,lastPr
        FROM snap_ticks
        GROUP BY instId
    ) t2 USING(instId)
    """)

    conn.commit()


# --------------------------------------------------
# Build trigger snapshot
# keep only best side / best signal per asset
# --------------------------------------------------

def fetch_trigger_snapshot(conn):

    rows = conn.execute("""
    WITH ranked AS (
        SELECT
            signal_uid,
            signal_ts,
            instId,
            side,
            entry_price,
            sector,
            alpha_score,
            universal_alpha,
            alpha_class,
            cross_asset_score,
            z_score,
            rank,
            leverage,
            notional_suggestion,
            qty_suggestion,
            ROW_NUMBER() OVER (
                PARTITION BY instId
                ORDER BY
                    alpha_score DESC,
                    cross_asset_score DESC,
                    universal_alpha DESC,
                    rank ASC
            ) AS rn
        FROM out_triggers
    )
    SELECT
        signal_uid,
        signal_ts,
        instId,
        side,
        entry_price,
        sector,
        alpha_score,
        universal_alpha,
        alpha_class,
        cross_asset_score,
        z_score,
        rank,
        leverage,
        notional_suggestion,
        qty_suggestion
    FROM ranked
    WHERE rn = 1
    ORDER BY rank
    """).fetchall()

    return rows


def snapshot_signature(rows):

    payload = []
    for r in rows:
        payload.append(
            "|".join([
                str(r["instId"]),
                str(r["side"]),
                str(r["entry_price"]),
                str(r["alpha_score"]),
                str(r["universal_alpha"]),
                str(r["cross_asset_score"]),
                str(r["rank"]),
                str(r["leverage"]),
                str(r["notional_suggestion"]),
            ])
        )

    raw = "\n".join(payload).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()


# --------------------------------------------------
# Refresh triggers cache only if changed
# --------------------------------------------------

def refresh_triggers_live(conn, last_signature):

    rows = fetch_trigger_snapshot(conn)
    new_signature = snapshot_signature(rows)

    if new_signature == last_signature:
        return last_signature, 0, False

    conn.execute("DELETE FROM triggers_live")

    conn.executemany("""
    INSERT INTO triggers_live (
        signal_uid,
        signal_ts,
        instId,
        side,
        entry_price,
        sector,
        alpha_score,
        universal_alpha,
        alpha_class,
        cross_asset_score,
        z_score,
        rank,
        leverage,
        notional_suggestion,
        qty_suggestion
    )
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, [
        (
            r["signal_uid"],
            r["signal_ts"],
            r["instId"],
            r["side"],
            r["entry_price"],
            r["sector"],
            r["alpha_score"],
            r["universal_alpha"],
            r["alpha_class"],
            r["cross_asset_score"],
            r["z_score"],
            r["rank"],
            r["leverage"],
            r["notional_suggestion"],
            r["qty_suggestion"],
        )
        for r in rows
    ])

    conn.commit()

    return new_signature, len(rows), True


# --------------------------------------------------
# Main loop
# --------------------------------------------------

def main():

    log.info("[BOOT] dec_writer started")
    print("dec_writer started", flush=True)

    dec_conn = conn_dec()

    last_tick = 0
    last_atr = 0
    last_signal = 0
    last_range = 0
    last_heartbeat = 0
    last_trigger_signature = None

    while True:

        try:

            tick_ts = latest_tick_ts()
            now = int(time.time() * 1000)

            if now - last_heartbeat > HEARTBEAT_MS:

                log.info("[HEARTBEAT] tick=%s", tick_ts)
                last_heartbeat = now


            # wait new tick
            if tick_ts <= last_tick:

                time.sleep(BASE_SLEEP)
                continue


            last_tick = tick_ts


            # -----------------------
            # Tick history
            # -----------------------

            update_tick_history(dec_conn)


            # -----------------------
            # Orderflow
            # -----------------------

            refresh_snap_orderflow(dec_conn)


            atr_rows = 0
            signal_rows = 0
            range_rows = 0
            ext_rows = 0
            cluster_rows = 0


            # ATR
            if now - last_atr > 1000:

                atr_rows = refresh_snap_atr()
                last_atr = now


            # signal
            if now - last_signal > 2000:

                signal_rows = refresh_signal_history()
                last_signal = now


            # range / cluster
            if now - last_range > 45000:

                stats = refresh_snap_range()

                range_rows = stats.get("rows", 0)

                ext_rows = refresh_snap_range_ext()

                cluster_rows = refresh_cluster_history()

                last_range = now


            # -----------------------
            # Refresh trigger cache
            # only if changed
            # one best signal per asset
            # -----------------------

            last_trigger_signature, trig_rows, trig_changed = refresh_triggers_live(
                dec_conn,
                last_trigger_signature
            )


            log.info(
                "[DEC] tick=%d atr=%d signal=%d range=%d ext=%d cluster=%d triggers=%d changed=%s",
                tick_ts,
                atr_rows,
                signal_rows,
                range_rows,
                ext_rows,
                cluster_rows,
                trig_rows,
                int(trig_changed)
            )


        except Exception:

            log.exception("[DEC_RUNTIME_ERROR]")


        time.sleep(BASE_SLEEP)


if __name__ == "__main__":
    main()

