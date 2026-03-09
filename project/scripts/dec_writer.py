#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCALP — DEC WRITER (SPLIT / SAFE / DEBUG)

- log AVANT tout
- imports protégés
"""

import logging
import secrets
import sys
import time
import yaml
import sqlite3
from pathlib import Path
from datetime import datetime

LOG_PATH = "/opt/scalp/project/logs/dec_writer.log"

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s DEC %(levelname)s %(message)s"
)
log = logging.getLogger("DEC")

log.info("[BOOT] dec_writer starting")

try:
    from dec_ctx import load_ctx
    from dec_atr import refresh_snap_atr
    from dec_market import load_market_ok, market_pass
    from dec_range import refresh_snap_range
except Exception as e:
    log.exception("[BOOT_IMPORT_ERR]")
    raise


ROOT = Path("/opt/scalp/project")
DB_DEC = ROOT / "data/dec.db"
CFG_PATH = ROOT / "conf/dec.yaml"
LOOP_SLEEP = 2.0
RANGE_REFRESH_INTERVAL_S = 45

CFG = yaml.safe_load(open(CFG_PATH))["dec"]


def conn():
    c = sqlite3.connect(str(DB_DEC), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    return c


def now_ms():
    return int(time.time() * 1000)


def build_uid(instId, side):
    symbol = str(instId or "").split("/")[0]
    hhmmss = datetime.utcnow().strftime("%H%M%S")
    rand4 = secrets.token_hex(2)
    return f"{symbol}-{side}-{hhmmss}-{rand4}"


def ensure_uid_column(c):
    cols = {r["name"] for r in c.execute("PRAGMA table_info(snap_ctx)").fetchall()}
    if "uid" not in cols:
        c.execute("ALTER TABLE snap_ctx ADD COLUMN uid TEXT")


def ensure_v_dec_fire_view(c):
    c.execute("DROP VIEW IF EXISTS v_dec_fire")
    c.execute("""
        CREATE VIEW v_dec_fire AS
        WITH base AS (
            SELECT
                s.uid,
                s.instId,
                s.side,
                s.ctx,
                s.score_C,
                s.atr_fast,
                s.atr_slow,
                s.vol_regime,
                t.lastPr,
                s.ts_updated
            FROM snap_ctx s
            JOIN ticks_live t
              ON t.instId = s.instId
            WHERE s.ctx_ok = 1
        ),
        patterned AS (
            SELECT *,
                CASE
                    WHEN ctx='bullish' AND vol_regime='EXPAND'  THEN 'MOMENTUM'
                    WHEN ctx='bullish' AND vol_regime='NORMAL'  THEN 'CONT'
                    WHEN ctx='bearish' AND vol_regime='NORMAL'  THEN 'DRIFT'
                    WHEN ctx='bearish' AND vol_regime='COMPRESS' THEN 'PREBREAK'
                    ELSE 'IGNORE'
                END AS dec_mode
            FROM base
        ),
        admission AS (
            SELECT *,
                CASE
                    WHEN dec_mode='MOMENTUM' AND ABS(score_C)>=0.45 THEN 1
                    WHEN dec_mode='PREBREAK' THEN 1
                    WHEN dec_mode='DRIFT' AND ABS(score_C)>=0.30 THEN 1
                    WHEN dec_mode='CONT'  AND ABS(score_C)>=0.30 THEN 1
                    ELSE 0
                END AS fire
            FROM patterned
        )
        SELECT
            uid, instId, side, lastPr, atr_fast AS atr,
            dec_mode, score_C, ctx, fire
        FROM admission
        WHERE fire=1
    """)


def main():
    log.info("[START] dec_writer loop")
    last_range_refresh_ms = 0
    cfg_range = CFG.get("range", {}) if isinstance(CFG, dict) else {}
    range_refresh_interval_s = float(cfg_range.get("refresh_interval_s", RANGE_REFRESH_INTERVAL_S))

    while True:
        try:
            ts = now_ms()

            if ts - last_range_refresh_ms >= int(range_refresh_interval_s * 1000):
                range_stats = refresh_snap_range()
                last_range_refresh_ms = ts
                log.info(
                    "[RANGE_REFRESH] rows=%d skipped_short=%d skipped_invalid=%d lag_ms=%s stale_rows=%d is_stale=%s duration_ms=%d",
                    range_stats.get("rows", 0),
                    range_stats.get("skipped_short", 0),
                    range_stats.get("skipped_invalid", 0),
                    str(range_stats.get("lag_ms")),
                    range_stats.get("stale_rows", 0),
                    str(range_stats.get("is_stale", False)),
                    range_stats.get("duration_ms", 0),
                )

            ctx_rows = load_ctx()
            atr_rows = refresh_snap_atr()
            market   = load_market_ok()

            with conn() as c:
                ensure_uid_column(c)
                ensure_v_dec_fire_view(c)
                c.execute("DELETE FROM snap_ctx")

                out = []
                veto = 0

                for r in ctx_rows:
                    m = market.get(r["instId"])
                    if not m or not market_pass(m, CFG["market_veto"]):
                        veto += 1
                        continue

                    out.append((
                        build_uid(r["instId"], r["side"]),
                        r["instId"],
                        r["ctx"],
                        r["score_C"],
                        r["side"],
                        None,
                        None,
                        "UNKNOWN",
                        1,
                        ts
                    ))

                if out:
                    c.executemany("""
                        INSERT INTO snap_ctx (
                            uid,
                            instId, ctx, score_C, side,
                            atr_fast, atr_slow, vol_regime,
                            ctx_ok, ts_updated
                        ) VALUES (?,?,?,?,?,?,?,?,?,?)
                    """, out)

                c.execute("""
                    UPDATE snap_ctx
                    SET
                        atr_fast = (
                            SELECT atr_1m FROM snap_atr a
                            WHERE a.instId = snap_ctx.instId
                        ),
                        atr_slow = (
                            SELECT atr_5m FROM snap_atr a
                            WHERE a.instId = snap_ctx.instId
                        ),
                        vol_regime = (
                            SELECT vol_regime FROM snap_atr a
                            WHERE a.instId = snap_ctx.instId
                        )
                """)

                c.execute("""
                    UPDATE snap_ctx
                    SET
                        atr_fast = COALESCE(atr_fast, atr_slow),
                        vol_regime = COALESCE(vol_regime, 'NORMAL')
                """)

            log.info("[UPDATE] ctx=%d snap=%d veto=%d atr_rows=%d",
                     len(ctx_rows), len(out), veto, atr_rows)

        except Exception:
            log.exception("[RUNTIME_ERR]")

        time.sleep(LOOP_SLEEP)


if __name__ == "__main__":
    main()
