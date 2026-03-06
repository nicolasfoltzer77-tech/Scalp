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
    from dec_atr import load_atr_map, select_atr
    from dec_market import load_market_ok, market_pass
except Exception as e:
    log.exception("[BOOT_IMPORT_ERR]")
    raise


ROOT = Path("/opt/scalp/project")
DB_DEC = ROOT / "data/dec.db"
CFG_PATH = ROOT / "conf/dec.yaml"
LOOP_SLEEP = 2.0

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

    while True:
        try:
            ts = now_ms()

            ctx_rows = load_ctx()
            atr_map  = load_atr_map()
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

                    atr_fast, atr_slow, vol = select_atr(
                        r["ctx"],
                        atr_map.get(r["instId"])
                    )

                    out.append((
                        build_uid(r["instId"], r["side"]),
                        r["instId"],
                        r["ctx"],
                        r["score_C"],
                        r["side"],
                        atr_fast,
                        atr_slow,
                        vol,
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

            log.info("[UPDATE] ctx=%d snap=%d veto=%d",
                     len(ctx_rows), len(out), veto)

        except Exception:
            log.exception("[RUNTIME_ERR]")

        time.sleep(LOOP_SLEEP)


if __name__ == "__main__":
    main()
