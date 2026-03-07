#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Manual test utility for TRIGGERS -> GEST ingestion.

- Reads triggers where status='fire'
- Inserts into gest with status='open_req'
- Keeps original uid (no regeneration)
- Emits debug logs to stdout and logs/gest.log
"""

import logging
import sqlite3
import traceback
from pathlib import Path

ROOT = Path("/opt/scalp/project")
DB_TRIG = ROOT / "data/triggers.db"
DB_GEST = ROOT / "data/gest.db"
LOG_PATH = ROOT / "logs/gest.log"


def conn(db_path: Path) -> sqlite3.Connection:
    c = sqlite3.connect(str(db_path), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c


def table_columns(c: sqlite3.Connection, table: str):
    rows = c.execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"] for r in rows}


def rget(row: sqlite3.Row, col: str, default=None):
    try:
        return row[col]
    except Exception:
        return default


def setup_logger() -> logging.Logger:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("GEST_TEST")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = logging.FileHandler(str(LOG_PATH))
    file_handler.setFormatter(fmt)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def run() -> int:
    log = setup_logger()
    t = conn(DB_TRIG)
    g = conn(DB_GEST)

    inserted = 0
    try:
        trig_cols = table_columns(t, "triggers")
        gest_cols = table_columns(g, "gest")

        rows = t.execute(
            """
            SELECT *
            FROM triggers
            WHERE status = 'fire'
            ORDER BY ts
            LIMIT 10
            """
        ).fetchall()

        log.info("GEST POLL → found %d triggers", len(rows))
        print(f"Triggers found: {len(rows)}")

        for r in rows:
            uid = r["uid"]
            if g.execute("SELECT 1 FROM gest WHERE uid=?", (uid,)).fetchone():
                log.info("GEST SKIP duplicate uid uid=%s", uid)
                continue

            log.info(
                "GEST CONSUME: uid=%s instId=%s side=%s",
                uid,
                rget(r, "instId"),
                rget(r, "side"),
            )

            values = {
                "uid": uid,
                "instId": rget(r, "instId"),
                "side": rget(r, "side"),
                "entry_reason": rget(r, "entry_reason"),
                "score_C": rget(r, "score_C"),
                "score_S": rget(r, "score_S"),
                "score_H": rget(r, "score_H"),
                "score_M": rget(r, "score_M"),
                "score_of": rget(r, "score_of"),
                "score_mo": rget(r, "score_mo"),
                "score_br": rget(r, "score_br"),
                "score_force": rget(r, "score_force"),
                "trigger_type": rget(r, "trigger_type", rget(r, "type_signal", rget(r, "phase"))),
                "dec_mode": rget(r, "dec_mode"),
                "momentum_ok": rget(r, "momentum_ok"),
                "prebreak_ok": rget(r, "prebreak_ok"),
                "pullback_ok": rget(r, "pullback_ok"),
                "compression_ok": rget(r, "compression_ok"),
                "entry": rget(r, "price") if "price" in trig_cols else None,
                "price_signal": rget(r, "price") if "price" in trig_cols else None,
                "atr_signal": rget(r, "atr") if "atr" in trig_cols else None,
                "ts_signal": rget(r, "ts") if "ts" in trig_cols else None,
                "ts_open": rget(r, "ts_fire") if "ts_fire" in trig_cols else None,
                "status": "open_req",
            }
            insert_cols = [c for c in values if c in gest_cols]
            placeholders = ", ".join("?" for _ in insert_cols)
            g.execute(
                f"INSERT INTO gest ({', '.join(insert_cols)}) VALUES ({placeholders})",
                tuple(values[c] for c in insert_cols),
            )
            inserted += 1
            log.info("GEST INSERT OK: uid=%s", uid)

        g.commit()
        print(f"Inserted into gest: {inserted}")
        return inserted
    except Exception:
        log.error("GEST ERROR while test ingest")
        log.error(traceback.format_exc())
        raise
    finally:
        t.close()
        g.close()


if __name__ == "__main__":
    run()
