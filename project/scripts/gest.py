#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import time
import logging
from pathlib import Path

ROOT = Path("/opt/scalp/project")

DB_GEST     = ROOT / "data/gest.db"
DB_TRIGGERS = ROOT / "data/triggers.db"
DB_FOLLOWER = ROOT / "data/follower.db"
DB_OPENER   = ROOT / "data/opener.db"
DB_CLOSER   = ROOT / "data/closer.db"

LOOP_SLEEP = 0.2

log = logging.getLogger("GEST")


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
                cur = g.execute("""
                    UPDATE gest
                    SET status='open_done',
                        step=COALESCE(?, step),
                        ts_status_update=strftime('%s','now')*1000
                    WHERE uid=?
                      AND status='open_stdby'
                """, (r["step"], uid))
                if cur.rowcount:
                    log.info("[GEST ACK] uid=%s open_stdby -> open_done", uid)
            elif st == "pyramide_done":
                cur = g.execute("""
                    UPDATE gest
                    SET status='pyramide_done',
                        step=COALESCE(?, step),
                        ts_status_update=strftime('%s','now')*1000
                    WHERE uid=?
                      AND status='pyramide_req'
                """, (r["step"], uid))
                if cur.rowcount:
                    log.info("[GEST ACK] uid=%s pyramide_req -> pyramide_done", uid)
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
        close_done_uids = c.execute("""
            SELECT uid
            FROM closer
            WHERE status='close_done'
        """).fetchall()

        for r in close_done_uids:
            cur = g.execute("""
                UPDATE gest
                SET status='close_done',
                    ts_status_update=strftime('%s','now')*1000
                WHERE uid=?
                  AND status='close_req'
            """, (r["uid"],))
            if cur.rowcount:
                log.info("[GEST ACK] uid=%s close_req -> close_done", r["uid"])

        partial_done_uids = c.execute("""
            SELECT uid
            FROM closer
            WHERE status='partial_done'
        """).fetchall()

        for r in partial_done_uids:
            cur = g.execute("""
                UPDATE gest
                SET status='partial_done',
                    ts_status_update=strftime('%s','now')*1000
                WHERE uid=?
                  AND status='partial_req'
            """, (r["uid"],))
            if cur.rowcount:
                log.info("[GEST ACK] uid=%s partial_req -> partial_done", r["uid"])
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
                log.info("[GEST FOLLOW] uid=%s -> follow", uid)
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
        follower_cols = table_columns(f, "follower")
        has_fsm_cols = "req_step" in follower_cols and "done_step" in follower_cols

        rows = f.execute("""
            SELECT uid, status,
                   ratio_to_close,
                   ratio_to_add,
                   reason,
                   req_step,
                   done_step
            FROM follower
            WHERE status IN ('pyramide_req','partial_req','close_req')
        """).fetchall()

        # Follower peut envoyer une nouvelle requête juste après un ACK *_done,
        # avant que mirror_follower_follow() n'ait eu le temps de repasser
        # gest.status à "follow". On accepte les états *_done comme base valide
        # uniquement quand req_step/done_step existent (FSM récente).
        req_from_done_allowed = has_fsm_cols
        for r in rows:
            uid = r["uid"]
            st  = r["status"]

            # Ignore stale follower requests that were already ACKed upstream.
            # Without this guard, gest can be downgraded from *_done -> *_req
            # in the same loop when follower status lags behind.
            if has_fsm_cols:
                req_step = int(r["req_step"] or 0)
                done_step = int(r["done_step"] or 0)
                if req_step <= done_step:
                    continue

            if st == "pyramide_req":
                base_statuses = ["follow", "open_done", "partial_done", "partialdone"]
                if req_from_done_allowed:
                    base_statuses.append("pyramide_done")
                placeholders = ",".join(["?"] * len(base_statuses))
                cur = g.execute("""
                    UPDATE gest
                    SET status='pyramide_req',
                        ratio_to_add=?,
                        reason=?,
                        ts_status_update=strftime('%s','now')*1000
                    WHERE uid=?
                      AND status IN (""" + placeholders + """)
                """, (r["ratio_to_add"], r["reason"], uid, *base_statuses))
                if cur.rowcount:
                    log.info("[GEST REQ] uid=%s -> pyramide_req", uid)

            elif st == "partial_req":
                cur = g.execute("""
                    UPDATE gest
                    SET status='partial_req',
                        ratio_to_close=?,
                        reason=?,
                        ts_status_update=strftime('%s','now')*1000
                    WHERE uid=?
                      AND status IN ('follow','open_done','pyramide_done','partial_done','partialdone')
                """, (r["ratio_to_close"], r["reason"], uid))
                if cur.rowcount:
                    log.info("[GEST REQ] uid=%s -> partial_req", uid)

            elif st == "close_req":
                cur = g.execute("""
                    UPDATE gest
                    SET status='close_req',
                        ratio_to_close=1.0,
                        reason=?,
                        ts_status_update=strftime('%s','now')*1000
                    WHERE uid=?
                      AND status IN ('follow','open_done','pyramide_done','partial_done','partialdone')
                """, (r["reason"], uid))
                if cur.rowcount:
                    log.info("[GEST REQ] uid=%s -> close_req", uid)
    finally:
        f.close()
        g.close()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log.info("[START] gest loop sleep=%.3fs", LOOP_SLEEP)

    while True:
        try:
            ingest_triggers()
            ingest_opener_done()
            ingest_closer_done()
            mirror_follower_follow()
            ingest_follower_requests()
        except Exception as e:
            log.exception("[GEST ERROR] %s", e)

        time.sleep(LOOP_SLEEP)


if __name__ == "__main__":
    main()
