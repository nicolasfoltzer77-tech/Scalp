#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import time
from pathlib import Path

ROOT = Path("/opt/scalp/project")

DB_GEST     = ROOT / "data/gest.db"
DB_TRIGGERS = ROOT / "data/triggers.db"
DB_FOLLOWER = ROOT / "data/follower.db"
DB_OPENER   = ROOT / "data/opener.db"
DB_CLOSER   = ROOT / "data/closer.db"

LOOP_SLEEP = 0.2


def conn(path):
    c = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA synchronous=NORMAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c


# -------------------------------------------------
# TRIGGERS → open_req (create trade)
# -------------------------------------------------
def ingest_triggers():
    t = conn(DB_TRIGGERS)
    g = conn(DB_GEST)

    try:
        rows = t.execute("""
            SELECT uid, instId, side, price, ts, ts_fire, atr
            FROM triggers
            WHERE status='fired'
        """).fetchall()

        for r in rows:
            uid = r["uid"]
            if g.execute("SELECT 1 FROM gest WHERE uid=?", (uid,)).fetchone():
                continue

            g.execute("""
                INSERT INTO gest
                (uid, instId, side, entry, price_signal,
                 atr_signal, ts_signal, ts_open, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open_req')
            """, (
                uid,
                r["instId"],
                r["side"],
                r["price"],
                r["price"],
                r["atr"],
                r["ts"],
                r["ts_fire"]
            ))
    finally:
        t.close()
        g.close()


# -------------------------------------------------
# OPENER ACK → *_done
# -------------------------------------------------
def ingest_opener_done():
    o = conn(DB_OPENER)
    g = conn(DB_GEST)

    try:
        rows = o.execute("""
            SELECT uid, status, step
            FROM opener
            WHERE status IN ('open_done','pyramide_done')
        """).fetchall()

        for r in rows:
            uid = r["uid"]
            st  = r["status"]

            if st == "open_done":
                g.execute("""
                    UPDATE gest
                    SET status='open_done',
                        step=COALESCE(?, step),
                        ts_status_update=strftime('%s','now')*1000
                    WHERE uid=?
                      AND status='open_req'
                """, (r["step"], uid))
            elif st == "pyramide_done":
                g.execute("""
                    UPDATE gest
                    SET status='pyramide_done',
                        step=COALESCE(?, step),
                        ts_status_update=strftime('%s','now')*1000
                    WHERE uid=?
                      AND status='pyramide_req'
                """, (r["step"], uid))
    finally:
        o.close()
        g.close()


# -------------------------------------------------
# CLOSER ACK → *_done
# -------------------------------------------------
def ingest_closer_done():
    c = conn(DB_CLOSER)
    g = conn(DB_GEST)

    try:
        rows = c.execute("""
            SELECT uid, status
            FROM closer
            WHERE status IN ('close_done','partial_done')
        """).fetchall()

        for r in rows:
            uid = r["uid"]
            st  = r["status"]

            if st == "partial_done":
                g.execute("""
                    UPDATE gest
                    SET status='partial_done',
                        ts_status_update=strftime('%s','now')*1000
                    WHERE uid=?
                      AND status='partial_req'
                """, (uid,))
            elif st == "close_done":
                g.execute("""
                    UPDATE gest
                    SET status='close_done',
                        ts_status_update=strftime('%s','now')*1000
                    WHERE uid=?
                      AND status='close_req'
                """, (uid,))
    finally:
        c.close()
        g.close()


# -------------------------------------------------
# FOLLOWER MIRROR → follow
# -------------------------------------------------
def mirror_follower_follow():
    f = conn(DB_FOLLOWER)
    g = conn(DB_GEST)

    try:
        rows = f.execute("""
            SELECT uid, step
            FROM follower
            WHERE status='follow'
        """).fetchall()

        for r in rows:
            uid = r["uid"]
            g.execute("""
                UPDATE gest
                SET status='follow',
                    step=COALESCE(?, step),
                    ts_status_update=strftime('%s','now')*1000
                WHERE uid=?
                  AND status LIKE '%_done'
            """, (r["step"], uid))
    finally:
        f.close()
        g.close()


# -------------------------------------------------
# FOLLOWER REQUESTS → *_req  (RATIO SYNC FIX + STEP FIX)
# -------------------------------------------------
def ingest_follower_requests():
    f = conn(DB_FOLLOWER)
    g = conn(DB_GEST)

    try:
        rows = f.execute("""
            SELECT uid, status,
                   ratio_to_close,
                   ratio_to_add
            FROM follower
            WHERE status IN ('pyramide_req','partial_req','close_req')
        """).fetchall()

        for r in rows:
            uid = r["uid"]
            st  = r["status"]

            if st == "pyramide_req":
                g.execute("""
                    UPDATE gest
                    SET status='pyramide_req',
                        ratio_to_add=?,
                        ts_status_update=strftime('%s','now')*1000
                    WHERE uid=?
                      AND status='follow'
                """, (r["ratio_to_add"], uid))

            elif st == "partial_req":
                g.execute("""
                    UPDATE gest
                    SET status='partial_req',
                        ratio_to_close=?,
                        ts_status_update=strftime('%s','now')*1000
                    WHERE uid=?
                      AND status='follow'
                """, (r["ratio_to_close"], uid))

            elif st == "close_req":
                g.execute("""
                    UPDATE gest
                    SET status='close_req',
                        ratio_to_close=1.0,
                        ts_status_update=strftime('%s','now')*1000
                    WHERE uid=?
                      AND status='follow'
                """, (uid,))
    finally:
        f.close()
        g.close()


def main():
    while True:
        try:
            ingest_triggers()
            ingest_opener_done()
            ingest_closer_done()
            mirror_follower_follow()
            ingest_follower_requests()
        except Exception as e:
            print("[GEST ERROR]", e)

        time.sleep(LOOP_SLEEP)


if __name__ == "__main__":
    main()

