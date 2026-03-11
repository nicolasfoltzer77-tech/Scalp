#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import time
import logging
from pathlib import Path

ROOT = Path("/opt/scalp/project")

DB_DEC  = ROOT / "data/dec.db"
DB_TRIG = ROOT / "data/triggers.db"

LOG = ROOT / "logs/triggers.log"

ENGINE_SLEEP = 0.2
MAX_SIGNALS_PER_CYCLE = 10

ASSET_COOLDOWN_SEC = 30


logging.basicConfig(
    filename=str(LOG),
    level=logging.INFO,
    format="%(asctime)s TRIG %(levelname)s %(message)s",
)

log = logging.getLogger("TRIG")


# ------------------------------------------------
# helpers
# ------------------------------------------------

def now_ms():
    return int(time.time() * 1000)


def conn(db):

    c = sqlite3.connect(str(db), timeout=10)
    c.row_factory = sqlite3.Row

    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")

    return c


# ------------------------------------------------
# read signals from DEC cache
# ------------------------------------------------

def read_signals():

    with conn(DB_DEC) as d:

        rows = d.execute(
            """
            SELECT
            signal_uid,
            signal_ts,
            instId,
            side,
            entry_price,
            leverage,
            notional_suggestion,
            alpha_score,
            rank
            FROM triggers_live
            ORDER BY rank
            LIMIT ?
            """,
            (MAX_SIGNALS_PER_CYCLE,),
        ).fetchall()

    return rows


# ------------------------------------------------
# active trigger check
# ------------------------------------------------

def inst_active(db, instId):

    r = db.execute(
        """
        SELECT 1
        FROM trigger_queue
        WHERE instId = ?
        AND status IN ('NEW','INGESTED')
        LIMIT 1
        """,
        (instId,),
    ).fetchone()

    return r is not None


# ------------------------------------------------
# cooldown check
# ------------------------------------------------

def cooldown_active(db, instId):

    r = db.execute(
        """
        SELECT ts_created
        FROM trigger_queue
        WHERE instId = ?
        ORDER BY ts_created DESC
        LIMIT 1
        """,
        (instId,),
    ).fetchone()

    if not r:
        return False

    last_ts = r["ts_created"]

    delta = (now_ms() - last_ts) / 1000

    return delta < ASSET_COOLDOWN_SEC


# ------------------------------------------------
# insert trigger
# ------------------------------------------------

def push_trigger(db, row):

    symbol = row["instId"]

    if inst_active(db, symbol):
        return False

    if cooldown_active(db, symbol):
        return False

    uid = row["signal_uid"]
    side = row["side"]

    notional = row["notional_suggestion"]
    leverage = row["leverage"]

    margin = notional / leverage if leverage else notional

    ts = now_ms()

    db.execute(
        """
        INSERT INTO trigger_queue (

        uid,
        instId,
        side,

        entry_price,
        leverage,

        margin_usd,
        position_size,

        alpha,

        status,

        ts_signal,
        ts_created

        )

        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            uid,
            symbol,
            side,

            row["entry_price"],
            leverage,

            margin,
            notional,

            row["alpha_score"],

            "NEW",

            row["signal_ts"],
            ts,
        ),
    )

    log.info(
        "TRIGGER %s %s rank=%d alpha=%.3f",
        symbol,
        side,
        row["rank"],
        row["alpha_score"],
    )

    return True


# ------------------------------------------------
# cycle
# ------------------------------------------------

def run_cycle():

    signals = read_signals()

    if not signals:
        return 0

    inserted = 0

    with conn(DB_TRIG) as t:

        for s in signals:

            if push_trigger(t, s):
                inserted += 1

        t.commit()

    return inserted


# ------------------------------------------------
# engine
# ------------------------------------------------

def main():

    log.info("Trigger engine started")

    while True:

        try:

            inserted = run_cycle()

            if inserted:
                log.info("cycle inserted=%d", inserted)

        except Exception:
            log.exception("ENGINE ERROR")

        time.sleep(ENGINE_SLEEP)


if __name__ == "__main__":
    main()

