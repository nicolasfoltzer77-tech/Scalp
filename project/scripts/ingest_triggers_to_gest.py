#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCALP — INGEST TRIGGERS → GEST (FINAL / SNAPSHOT SAFE)

RÔLE :
- lit triggers.db (read-only)
- écrit gest.db (SEUL writer)
- snapshot COMPLET du signal
- crée open_req avec entry NON NULL
"""

import sqlite3
import time
import logging
from pathlib import Path

# =============================================================================
# PATHS
# =============================================================================

ROOT = Path("/opt/scalp/project")

DB_TRIG = ROOT / "data/triggers.db"
DB_GEST = ROOT / "data/gest.db"

LOG = ROOT / "logs/ingest_triggers.log"
LOOP_SLEEP = 0.3

# =============================================================================
# LOG
# =============================================================================

logging.basicConfig(
    filename=str(LOG),
    level=logging.INFO,
    format="%(asctime)s INGEST %(levelname)s %(message)s"
)
log = logging.getLogger("INGEST")

# =============================================================================
# UTILS
# =============================================================================

def now_ms():
    return int(time.time() * 1000)

def conn(db):
    c = sqlite3.connect(str(db), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c

# =============================================================================
# CORE
# =============================================================================

def ingest():
    cT = conn(DB_TRIG)
    cG = conn(DB_GEST)

    rows = cT.execute("""
        SELECT
            uid,
            instId,
            side,
            price,
            atr,
            entry_reason,
            score_of
        FROM triggers
        WHERE status='fired'
    """).fetchall()

    if not rows:
        cT.close()
        cG.close()
        return

    now = now_ms()

    for t in rows:
        # idempotence
        if cG.execute(
            "SELECT 1 FROM gest WHERE uid=?",
            (t["uid"],)
        ).fetchone():
            continue

        if t["price"] is None or t["atr"] is None:
            log.warning("[SKIP] uid=%s price/atr NULL", t["uid"])
            continue

        cG.execute("""
            INSERT INTO gest (
                uid,
                instId,
                side,
                ts_open,
                entry,
                atr_signal,
                entry_reason,
                score_of,
                status
            ) VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            t["uid"],
            t["instId"],
            t["side"],
            now,
            float(t["price"]),       -- 🔑 SNAPSHOT ENTRY
            float(t["atr"]),         -- 🔑 SNAPSHOT ATR
            t["entry_reason"],
            t["score_of"],
            "open_req"
        ))

        log.info(
            "[OPEN_REQ] uid=%s %s %s entry=%.5f atr=%.5f",
            t["uid"],
            t["instId"],
            t["side"],
            t["price"],
            t["atr"]
        )

    cG.commit()
    cT.close()
    cG.close()

# =============================================================================
# MAIN
# =============================================================================

def main():
    log.info("[START] ingest triggers → gest")
    while True:
        try:
            ingest()
        except Exception as e:
            log.exception("[ERR]")
        time.sleep(LOOP_SLEEP)

if __name__ == "__main__":
    main()

