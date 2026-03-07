#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import time
import logging
from pathlib import Path

ROOT = Path("/opt/scalp/project")

DB_GEST     = ROOT / "data/gest.db"
DB_TRIGGERS = ROOT / "data/triggers.db"
DB_DEC      = ROOT / "data/dec.db"
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


def clamp01(value, default=0.0):
    try:
        x = float(value)
    except (TypeError, ValueError):
        x = float(default)
    return max(0.0, min(1.0, x))


def rget(row, col, default=None):
    try:
        return row[col]
    except Exception:
        return default


def ensure_gest_score_columns(g):
    existing = table_columns(g, "gest")
    required = {
        "score_C": "REAL",
        "score_S": "REAL",
        "score_H": "REAL",
        "score_M": "REAL",
        "score_of": "REAL",
        "score_mo": "REAL",
        "score_br": "REAL",
        "score_force": "REAL",
    }
    for col, col_type in required.items():
        if col not in existing:
            g.execute(f"ALTER TABLE gest ADD COLUMN {col} {col_type}")


def load_dec_payload(d_conn, uid, inst_id):
    objects = {r["name"] for r in d_conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')").fetchall()}
    if "v_dec_score_s" not in objects:
        return None

    dec_cols = table_columns(d_conn, "v_dec_score_s")
    wanted_cols = [
        "uid", "instId", "score_C", "ctx", "dec_mode", "compression_ok",
        "momentum_ok", "prebreak_ok", "pullback_ok", "score_S",
        "s_struct", "s_quality", "s_vol", "s_confirm",
    ]
    select_cols = [c for c in wanted_cols if c in dec_cols]
    if not select_cols:
        return None

    query = f"SELECT {', '.join(select_cols)} FROM v_dec_score_s WHERE uid=? LIMIT 1"
    row = d_conn.execute(query, (uid,)).fetchone()
    if row:
        return row

    if "instId" in dec_cols:
        query = f"""
            SELECT {', '.join(select_cols)}
            FROM v_dec_score_s
            WHERE instId=?
            ORDER BY COALESCE(ts_updated, 0) DESC
            LIMIT 1
        """
        return d_conn.execute(query, (inst_id,)).fetchone()
    return None


def resolve_score_h(t_conn, inst_id, trigger_type, dec_mode):
    trig_tables = {r["name"] for r in t_conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    if "historical_scores_v2" in trig_tables:
        hist_cols = table_columns(t_conn, "historical_scores_v2")
        h_col = "score_H" if "score_H" in hist_cols else ("score_H_final" if "score_H_final" in hist_cols else None)
        if h_col and all(c in hist_cols for c in ("instId", "type_signal", "ctx")):
            row = t_conn.execute(
                f"""
                SELECT {h_col} AS score_H
                FROM historical_scores_v2
                WHERE instId=? AND type_signal=? AND ctx=?
                ORDER BY COALESCE(ts_updated, 0) DESC
                LIMIT 1
                """,
                (inst_id, trigger_type, dec_mode),
            ).fetchone()
            if row and row["score_H"] is not None:
                return clamp01(row["score_H"], default=0.5)

    if "v_score_H" in trig_tables:
        v_cols = table_columns(t_conn, "v_score_H")
        if "score_H" in v_cols:
            filters = []
            params = []
            if "instId" in v_cols:
                filters.append("instId=?")
                params.append(inst_id)
            if "trigger_type" in v_cols:
                filters.append("trigger_type=?")
                params.append(trigger_type)
            if "dec_mode" in v_cols:
                filters.append("dec_mode=?")
                params.append(dec_mode)

            where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
            row = t_conn.execute(
                f"SELECT score_H FROM v_score_H {where_clause} LIMIT 1",
                tuple(params),
            ).fetchone()
            if row and row["score_H"] is not None:
                return clamp01(row["score_H"], default=0.5)

    return 0.5


# -------------------------------------------------
# TRIGGERS → open_req (create trade)
# -------------------------------------------------
def ingest_triggers():
    t = conn(DB_TRIGGERS)
    d = conn(DB_DEC)
    g = conn(DB_GEST)

    try:
        trig_cols = table_columns(t, "triggers")
        gest_cols = table_columns(g, "gest")
        ensure_gest_score_columns(g)
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

            dec_payload = load_dec_payload(d, uid, r["instId"])

            score_s = rget(r, "score_S")
            if score_s is None and dec_payload is not None:
                score_s = rget(dec_payload, "score_S")
            if score_s is None:
                s_struct = rget(r, "s_struct", rget(dec_payload, "s_struct", 0.0))
                s_quality = rget(r, "s_quality", rget(dec_payload, "s_quality", 0.0))
                s_vol = rget(r, "s_vol", rget(dec_payload, "s_vol", 0.0))
                s_confirm = rget(r, "s_confirm", rget(dec_payload, "s_confirm", 0.0))
                score_s = (
                    0.40 * float(s_struct or 0.0)
                    + 0.30 * float(s_quality or 0.0)
                    + 0.20 * float(s_vol or 0.0)
                    + 0.10 * float(s_confirm or 0.0)
                )
            score_s = clamp01(score_s)

            trigger_type = (
                rget(r, "trigger_type")
                or rget(r, "type_signal")
                or rget(r, "phase")
            )
            dec_mode = rget(r, "dec_mode", rget(dec_payload, "dec_mode"))
            score_h = resolve_score_h(t, r["instId"], trigger_type, dec_mode)
            score_m = clamp01(rget(r, "score_M", 0.5), default=0.5)

            score_c = rget(r, "score_C")
            if score_c is None:
                score_c = rget(r, "dec_score_C")
            if score_c is None:
                score_c = rget(dec_payload, "score_C")

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
                "score_C": score_c,
                "dec_score_C": r["dec_score_C"] if "dec_score_C" in trig_cols else None,
                "score_S": score_s,
                "score_of": r["score_of"] if "score_of" in trig_cols else None,
                "score_mo": r["score_mo"] if "score_mo" in trig_cols else None,
                "score_br": r["score_br"] if "score_br" in trig_cols else None,
                "score_H": r["score_H"] if "score_H" in trig_cols and r["score_H"] is not None else score_h,
                "score_M": score_m,
                "score_force": r["score_force"] if "score_force" in trig_cols else None,
                "reason": r["fire_reason"] if "fire_reason" in trig_cols else None,
                "entry_reason": r["entry_reason"] if "entry_reason" in trig_cols else None,
                "type_signal": trigger_type,
                "trigger_type": trigger_type,
                "dec_mode": dec_mode,
                "dec_ctx": r["ctx"] if "ctx" in trig_cols else rget(dec_payload, "ctx"),
                "momentum_ok": rget(r, "momentum_ok", rget(dec_payload, "momentum_ok")),
                "prebreak_ok": rget(r, "prebreak_ok", rget(dec_payload, "prebreak_ok")),
                "pullback_ok": rget(r, "pullback_ok", rget(dec_payload, "pullback_ok")),
                "compression_ok": rget(r, "compression_ok", rget(dec_payload, "compression_ok")),
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
            log.info(
                "GEST INSERT: uid=%s instId=%s C=%.4f S=%.4f H=%.4f M=%.4f",
                uid,
                r["instId"],
                float(score_c or 0.0),
                float(score_s or 0.0),
                float(values["score_H"] or 0.5),
                float(score_m or 0.5),
            )
    finally:
        t.close()
        d.close()
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
                      AND status IN ('open_stdby','open_req')
                """, (r["step"], uid))
                if cur.rowcount:
                    log.info("[GEST ACK] uid=%s open_req/open_stdby -> open_done", uid)
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
                   done_step,
                   mfe_price,
                   mae_price,
                   atr_signal,
                   mfe_ts,
                   mae_ts
            FROM follower
            WHERE status IN ('pyramide_req','partial_req','close_req')
        """).fetchall()

        for r in rows:
            uid = r["uid"]
            st  = r["status"]

            g_state = g.execute(
                "SELECT status, step FROM gest WHERE uid=? LIMIT 1",
                (uid,),
            ).fetchone()
            g_step = int(g_state["step"] or 0) if g_state else 0
            g_status = g_state["status"] if g_state else None

            # Contrat FSM pratique:
            # - état canonique = "follow"
            # - mais tolérer les états ACK (open_done/pyramide_done/partial_done)
            #   évite un deadlock de course quand follower repasse brièvement à
            #   follow puis enchaîne un nouveau *_req avant que le mirror gest
            #   n'ait eu le temps de remettre explicitement gest.status=follow.
            #   Dans ce cas, gest doit accepter le nouveau *_req au lieu de
            #   bloquer indéfiniment la ligne en pyramide_req côté follower.
            ready_statuses = {"follow", "open_done", "pyramide_done", "partial_done", "partialdone"}
            if g_status not in ready_statuses:
                continue

            # Ignore stale follower requests that were already ACKed upstream.
            # Without this guard, gest can be downgraded from *_done -> *_req
            # in the same loop when follower status lags behind.
            if has_fsm_cols:
                req_step = int(r["req_step"] or 0)
                done_step = int(r["done_step"] or 0)
                if req_step <= done_step:
                    continue

                # Anti-downgrade guard:
                # if gest is already at an equal/newer step, follower's *_req is stale
                # (common race: opener ACK lands before follower.done_step refresh).
                if req_step <= g_step:
                    continue
            # Pas de garde legacy supplémentaire nécessaire ici:
            # g_status est déjà forcé à "follow".

            if st == "pyramide_req":
                cur = g.execute("""
                    UPDATE gest
                    SET status='pyramide_req',
                        ratio_to_add=?,
                        reason=?,
                        ts_status_update=strftime('%s','now')*1000
                    WHERE uid=?
                      AND status IN ('follow','open_done','pyramide_done','partial_done','partialdone')
                """, (r["ratio_to_add"], r["reason"], uid))
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
                        mfe_price=COALESCE(?, mfe_price),
                        mae_price=COALESCE(?, mae_price),
                        atr_signal=COALESCE(?, atr_signal),
                        mfe_ts=COALESCE(?, mfe_ts),
                        mae_ts=COALESCE(?, mae_ts),
                        ts_status_update=strftime('%s','now')*1000
                    WHERE uid=?
                      AND status IN ('follow','open_done','pyramide_done','partial_done','partialdone')
                """, (
                    r["reason"],
                    r["mfe_price"],
                    r["mae_price"],
                    r["atr_signal"],
                    r["mfe_ts"],
                    r["mae_ts"],
                    uid,
                ))
                if cur.rowcount:
                    log.info("[GEST REQ] uid=%s -> close_req mfe=%s mae=%s atr=%s", uid, r["mfe_price"], r["mae_price"], r["atr_signal"])
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
