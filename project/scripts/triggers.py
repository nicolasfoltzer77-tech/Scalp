#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import time
import uuid
import yaml
import logging
from pathlib import Path
from datetime import datetime

ROOT = Path("/opt/scalp/project")

DB_DEC      = ROOT / "data/dec.db"
DB_TRIG     = ROOT / "data/triggers.db"
DB_GEST     = ROOT / "data/gest.db"
DB_RECORDER = ROOT / "data/recorder.db"
DB_TICKS    = ROOT / "data/t.db"

CONF_YAML = ROOT / "conf/triggers.yaml"
LOG = ROOT / "logs/triggers.log"

CFG = yaml.safe_load(open(CONF_YAML)).get("triggers", {})
ENGINE_SLEEP = float(CFG.get("engine_sleep", 0.5))
ARM_TTL_MS   = int(CFG.get("arm_ttl_ms", 120000))

logging.basicConfig(filename=str(LOG),
    level=logging.INFO,
    format="%(asctime)s TRIG %(levelname)s %(message)s")
log = logging.getLogger("TRIG")


def now_ms():
    return int(time.time() * 1000)

def conn(db):
    c = sqlite3.connect(str(db), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c


# 🔥 PRIX LIVE DIRECT (sans vue)
def live_price(instId):
    with conn(DB_TICKS) as c:
        r = c.execute("""
            SELECT lastPr
            FROM ticks_hist
            WHERE instId=?
            ORDER BY ts_ms DESC
            LIMIT 1
        """, (instId,)).fetchone()
        return float(r["lastPr"]) if r else None


def uid_exists_anywhere(uid):
    with conn(DB_GEST) as g:
        if g.execute("SELECT 1 FROM gest WHERE uid=? LIMIT 1", (uid,)).fetchone():
            return True
    with conn(DB_RECORDER) as r:
        if r.execute("SELECT 1 FROM recorder WHERE uid=? LIMIT 1", (uid,)).fetchone():
            return True
    return False


def instid_active(instId):
    with conn(DB_GEST) as g:
        return g.execute("""
            SELECT 1 FROM gest
            WHERE instId=?
              AND status NOT IN ('close_done','expired')
            LIMIT 1
        """, (instId,)).fetchone() is not None


def trigger_active(instId):
    with conn(DB_TRIG) as t:
        return t.execute("""
            SELECT 1 FROM triggers
            WHERE instId=?
              AND status='fired'
            LIMIT 1
        """, (instId,)).fetchone() is not None


def purge_expired_triggers(t, now):
    rows = t.execute("""
        SELECT uid, ts FROM triggers WHERE status='fired'
    """).fetchall()

    for r in rows:
        if now - int(r["ts"]) > ARM_TTL_MS:
            t.execute("UPDATE triggers SET status='expired' WHERE uid=?", (r["uid"],))
            log.info("[TTL_EXPIRE] %s", r["uid"])


def build_uid(instId, side):
    base = instId.split("/")[0]
    hhmmss = datetime.utcnow().strftime("%H%M%S")
    u4 = uuid.uuid4().hex[:4]
    return f"{base}-{side}-{hhmmss}-{u4}"


def load_dec_fires():
    with conn(DB_DEC) as c:
        return c.execute("""
            SELECT instId, side, atr, dec_mode, score_C, ctx
            FROM v_dec_fire
            WHERE fire = 1
        """).fetchall()


def write_triggers():
    now = now_ms()
    rows = load_dec_fires()
    if not rows:
        return

    with conn(DB_TRIG) as t:
        purge_expired_triggers(t, now)

        for r in rows:
            instId = r["instId"]
            side   = r["side"]
            atr    = r["atr"]
            mode   = r["dec_mode"] or "DEC"
            scoreC = float(r["score_C"] or 0.0)
            ctx    = r["ctx"]

            price = live_price(instId)  # 🔥 prix réel

            if not instId or side not in ("buy", "sell"):
                continue
            if price is None or atr is None or atr <= 0:
                continue
            if instid_active(instId) or trigger_active(instId):
                continue

            uid = build_uid(instId, side)
            if uid_exists_anywhere(uid):
                continue

            sc = abs(scoreC)
            score_of = sc
            score_mo = sc
            score_br = 0.45 if mode == "MOMENTUM" else 0.30
            score_force = min(1.0, 0.5 + sc)

            t.execute("""
                INSERT INTO triggers (
                    uid, instId, side, entry_reason,
                    score_of, score_mo, score_br, score_force,
                    price, atr, ts, status, ts_fire,
                    phase, fire_reason, ctx,
                    score_ctx, dec_score_C, dec_mode, ts_created
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                uid, instId, side,
                f"DEC:{mode}",
                score_of, score_mo, score_br, score_force,
                price, atr,
                now, "fired",
                now, "fire",
                f"DEC:{mode}",
                ctx,
                scoreC, scoreC, mode, now
            ))

            log.info("[FIRED] %s %s uid=%s price=%.6f", instId, side, uid, price)


def main():
    log.info("[START] triggers engine (DEC → TRIGGERS)")
    while True:
        try:
            write_triggers()
        except Exception:
            log.exception("[ERR]")
        time.sleep(ENGINE_SLEEP)


if __name__ == "__main__":
    main()

