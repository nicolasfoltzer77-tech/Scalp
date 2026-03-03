#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FSM SYNC — FOLLOWER

RÈGLE CANON :
- OPEN INITIAL :
    gest.status = open_done
    ⇒ follower créé (via ingest)
    ⇒ follower passe DIRECTEMENT en follow
    ⇒ AUCUNE vérification de step / req_step / done_step

- Les vérifications step / done_step
  NE S’APPLIQUENT QUE POUR :
    pyramide / partial / close
"""

import logging

log = logging.getLogger("FOLLOWER_FSM_SYNC")


DONE_ALIASES = {
    "pyramide_done",
    "pyramid_done",  # tolérance legacy
}

REQ_TO_DONE = {
    "pyramide_req": DONE_ALIASES,
    "partial_req": {"partial_done"},
    "close_req": {"close_done"},
}


def _norm_status(value):
    try:
        return str(value or "").strip().lower()
    except Exception:
        return ""


def _safe_int(row, key, default=0):
    try:
        val = row[key]
    except Exception:
        return int(default)
    try:
        return int(val or 0)
    except Exception:
        return int(default)


def _safe_float(row, key, default=0.0):
    try:
        val = row[key]
    except Exception:
        return float(default)
    try:
        return float(val or 0.0)
    except Exception:
        return float(default)


def sync_fsm_status(g, f, now):
    """
    g : connection gest.db (read)
    f : connection follower.db (write)
    now : timestamp ms
    """

    gest_cols = {r[1] for r in g.execute("PRAGMA table_info(gest)").fetchall()}
    has_gest_qty_open = "qty_open" in gest_cols

    rows = f.execute("""
        SELECT *
        FROM follower
    """).fetchall()

    for fr in rows:
        uid = fr["uid"]
        status = fr["status"]
        status_norm = _norm_status(status)
        step = _safe_int(fr, "step", default=0)

        if has_gest_qty_open:
            gr = g.execute("""
                SELECT status, step, qty, qty_open
                FROM gest
                WHERE uid=?
            """, (uid,)).fetchone()
        else:
            # Compat schéma legacy: certains déploiements n'ont pas gest.qty_open.
            gr = g.execute("""
                SELECT status, step, qty
                FROM gest
                WHERE uid=?
            """, (uid,)).fetchone()

        if not gr:
            continue

        g_status = gr["status"]
        g_status_norm = _norm_status(g_status)
        g_step = _safe_int(gr, "step", default=0)

        # ==================================================
        # CAS OPEN INITIAL — PRIORITAIRE, SANS AUCUNE CONDITION
        # ==================================================
        if status_norm == "open_stdby" and step == 0:
            f.execute("""
                UPDATE follower
                SET status='follow',
                    step=1,
                    last_transition_ts=?
                WHERE uid=?
            """, (now, uid))

            log.info("[FSM] OPEN → FOLLOW uid=%s", uid)
            continue

        # ==================================================
        # CAS POST-OPEN (PYRAMIDE / PARTIAL / CLOSE)
        # → ICI seulement on utilisera req_step / done_step
        # ==================================================
        req_step = _safe_int(fr, "req_step", default=0)
        done_step = _safe_int(fr, "done_step", default=0)

        # ACK done (pyramide / partial / close) : follower doit repasser en
        # follow dès que gest confirme le *_done correspondant.
        #
        # Règle de déblocage demandée en prod:
        # - si follower est en *_req
        # - il lit UNIQUEMENT gest.status
        # - dès que gest passe en *_done correspondant, follower revient en follow
        #
        # Tolérance orthographe legacy : pyramide_done / pyramid_done.
        expected_done = REQ_TO_DONE.get(status_norm)
        if expected_done and g_status_norm in expected_done:
            qty_open = _safe_float(gr, "qty_open", default=0.0)
            qty = _safe_float(gr, "qty", default=0.0)
            qty_snapshot = qty_open if qty_open > 0.0 else qty

            if status_norm == "pyramide_req":
                reason = "PYRAMIDE_DONE_ACK"
            elif status_norm == "partial_req":
                reason = "PARTIAL_DONE_ACK"
            elif status_norm == "close_req":
                reason = "CLOSE_DONE_ACK"
            else:
                reason = "DONE_ACK"

            f.execute("""
                UPDATE follower
                SET status='follow',
                    step=?,
                    req_step=CASE
                        WHEN done_step IS NULL THEN req_step
                        ELSE done_step
                    END,
                    qty_open_snapshot=?,
                    nb_pyramide=CASE
                        WHEN ?='pyramide_req' THEN COALESCE(nb_pyramide, 0) + 1
                        ELSE nb_pyramide
                    END,
                    nb_pyramide_ack=CASE
                        WHEN ?='pyramide_req' THEN COALESCE(nb_pyramide_ack, 0) + 1
                        ELSE nb_pyramide_ack
                    END,
                    reason=?,
                    last_action_ts=?
                WHERE uid=?
            """, (g_step, qty_snapshot, status_norm, status_norm, reason, now, uid))
            continue

        if req_step != done_step:
            continue

        # Transitions gérées ailleurs (fsm_guard / fsm_status)
        # Rien à faire ici pour l’instant
