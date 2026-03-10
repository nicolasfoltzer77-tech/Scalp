#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Trigger Engine
READ  : dec.db (v_triggers)
WRITE : triggers.db (trigger_queue)
"""

import sqlite3
import time
import hashlib
import logging
from pathlib import Path

ROOT = Path("/opt/scalp/project")

DB_DEC = ROOT / "data/dec.db"
DB_TRIG = ROOT / "data/triggers.db"

LOG = ROOT / "logs/triggers.log"

ENGINE_SLEEP = 0.5
MAX_SIGNALS_PER_CYCLE = 10


logging.basicConfig(
    filename=str(LOG),
    level=logging.INFO,
    format="%(asctime)s TRIG %(levelname)s %(message)s",
)

log = logging.getLogger("TRIG")


def now_ms():
    return int(time.time() * 1000)


def conn(db):
    c = sqlite3.connect(str(db), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    return c


def build_uid(symbol, side, ts):
    payload = f"{symbol}:{side}:{ts}".encode()
    return hashlib.sha1(payload).hexdigest()[:16]


def signal_exists(db, symbol, side):
    r = db.execute(
        """
        SELECT 1
        FROM trigger_queue
        WHERE instId=? AND side=? AND status IN ('NEW','SENT')
        LIMIT 1
        """,
        (symbol, side),
    ).fetchone()

    return r is not None


def read_signals():

    with conn(DB_DEC) as d:

        rows = d.execute(
            """
            SELECT
            instId,
            side,
            entry_price,
            leverage,
            margin_usd,
            position_size_usd,
            stop_price,
            take_profit,
            alpha,
            market_regime,
            session,
            signal_ts
            FROM v_triggers
            ORDER BY alpha DESC
            LIMIT ?
            """,
            (MAX_SIGNALS_PER_CYCLE,),
        ).fetchall()

    return rows


def push_trigger(db, row):

    symbol = row["instId"]
    side = row["side"]

    if signal_exists(db, symbol, side):
        return False

    ts = now_ms()

    uid = build_uid(symbol, side, ts)

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

        stop_price,
        take_profit,

        alpha,

        market_regime,
        session,

        status,

        ts_signal,
        ts_created

        )

        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            uid,
            symbol,
            side,

            row["entry_price"],
            row["leverage"],
            row["margin_usd"],
            row["position_size_usd"],

            row["stop_price"],
            row["take_profit"],

            row["alpha"],

            row["market_regime"],
            row["session"],

            "NEW",

            row["signal_ts"],
            ts,
        ),
    )

    log.info(
        "NEW TRIGGER %s %s alpha=%.3f",
        symbol,
        side,
        row["alpha"],
    )

    return True


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

