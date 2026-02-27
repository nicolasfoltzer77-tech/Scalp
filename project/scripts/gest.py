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


def table_columns(conn_, table):
    rows = conn_.execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"] for r in rows}


# -------------------------------------------------
# TRIGGERS → open_req (create trade)
# -------------------------------------------------
def ingest_triggers():
    t = conn(DB_TRIGGERS)
    g = conn(DB_GEST)

    try:
        trig_cols = table_columns(t, "triggers")
        gest_cols = table_columns(g, "gest")

        rows = t.execute("""
            SELECT *
            FROM triggers
            WHERE status='fire'
        """).fetchall()

        now_ms = int(time.time() * 1000)

        for r in rows:
            uid = r["uid"]
            if g.execute("SELECT 1 FROM gest WHERE uid=?", (uid,)).fetchone():
                continue

            values = {
                "uid": uid,
                "instId": r["instId"],
                "side": r["side"],
                "entry": r["price"] if "price" in trig_cols else None,
                "price_signal": r["price"] if "price" in trig_cols else None,
                "atr_signal": r["atr"] if "atr" in trig_cols else None,
                "ts_signal": r["ts"] if "ts" in trig_cols else None,
                "ts_open": r["ts_fire"] if "ts_fire" in trig_cols else None,
                # Scores/rationale propagated for opener sizing compatibility.
                "score_C": r["score_C"] if "score_C" in trig_cols else None,
                "dec_score_C": r["dec_score_C"] if "dec_score_C" in trig_cols else None,
                "score_S": r["score_S"] if "score_S" in trig_cols else None,
                "score_of": r["score_of"] if "score_of" in trig_cols else None,
                "score_H": r["score_H"] if "score_H" in trig_cols else None,
                "score_force": r["score_force"] if "score_force" in trig_cols else None,
                "reason": r["fire_reason"] if "fire_reason" in trig_cols else None,
                "entry_reason": r["entry_reason"] if "entry_reason" in trig_cols else None,
                "type_signal": r["trigger_type"] if "trigger_type" in trig_cols else None,
                "dec_mode": r["dec_mode"] if "dec_mode" in trig_cols else None,
                "dec_ctx": r["ctx"] if "ctx" in trig_cols else None,
                "status": "open_stdby",
                "step": 0,
                "ts_created": now_ms,
                "ts_updated": now_ms,
            }

            insert_cols = [c for c in values if c in gest_cols]
            placeholders = ", ".join(["?"] * len(insert_cols))
            g.execute(
                f"INSERT INTO gest ({', '.join(insert_cols)}) VALUES ({placeholders})",
                tuple(values[c] for c in insert_cols),
            )
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
                      AND status='open_stdby'
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
                # Règle FSM stricte : une demande close_req ne doit JAMAIS
                # redescendre en partial_done. Si closer renvoie partial_done
                # (ex: fallback legacy), on force close_done côté gest.
                g.execute("""
                    UPDATE gest
                    SET status='close_done',
                        ts_status_update=strftime('%s','now')*1000
                    WHERE uid=?
                      AND status='close_req'
                """, (uid,))

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
            cur = g.execute("""
                UPDATE gest
                SET status='follow',
                    step=COALESCE(?, step),
                    ts_status_update=strftime('%s','now')*1000
                WHERE uid=?
                  AND status IN ('open_done','pyramide_done','partial_done','partialdone')
            """, (r["step"], uid))

            # Compat legacy: certains environnements ont déjà utilisé "partialdone"
            # (sans underscore). Dans tous les cas, follower=follow est canonique.
            if cur.rowcount:
                print(f"[GEST FOLLOW] uid={uid} -> follow")
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
                   ratio_to_add,
                   reason
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
                        reason=?,
                        ts_status_update=strftime('%s','now')*1000
                    WHERE uid=?
                      AND status='follow'
                """, (r["ratio_to_add"], r["reason"], uid))

            elif st == "partial_req":
                g.execute("""
                    UPDATE gest
                    SET status='partial_req',
                        ratio_to_close=?,
                        reason=?,
                        ts_status_update=strftime('%s','now')*1000
                    WHERE uid=?
                      AND status='follow'
                """, (r["ratio_to_close"], r["reason"], uid))

            elif st == "close_req":
                g.execute("""
                    UPDATE gest
                    SET status='close_req',
                        ratio_to_close=1.0,
                        reason=?,
                        ts_status_update=strftime('%s','now')*1000
                    WHERE uid=?
                      AND status='follow'
                """, (r["reason"], uid))
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
