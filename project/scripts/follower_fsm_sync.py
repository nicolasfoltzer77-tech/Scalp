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

        # ACK done (pyramide / partial) : follower doit repasser en follow,
        # recopier le step canonique et rafraîchir le snapshot de quantité.
        #
        # Règle de déblocage demandée en prod:
        # - si follower est en *_req
        # - il lit UNIQUEMENT gest.status
        # - dès que gest passe en *_done correspondant, follower revient en follow
        #
        # Ici on tolère les deux orthographes historiques:
        # pyramide_done / pyramid_done.
        if status_norm in ("pyramide_req", "pyramide_done") and g_status_norm in DONE_ALIASES:
            qty_open = _safe_float(gr, "qty_open", default=0.0)
            qty = _safe_float(gr, "qty", default=0.0)
            qty_snapshot = qty_open if qty_open > 0.0 else qty

            f.execute("""
                UPDATE follower
                SET status='follow',
                    step=?,
                    req_step=CASE
                        WHEN done_step IS NULL THEN req_step
                        ELSE done_step
                    END,
                    qty_open_snapshot=?,
                    nb_pyramide=COALESCE(nb_pyramide, 0) + 1,
                    nb_pyramide_ack=COALESCE(nb_pyramide_ack, 0) + 1,
                    reason='PYRAMIDE_DONE_ACK',
                    last_action_ts=?
                WHERE uid=?
            """, (g_step, qty_snapshot, now, uid))
            continue

        # Sur partial_done, on garde l'ack strict depuis partial_req.
        if g_status_norm == "partial_done" and status_norm in ("partial_req", "partial_done"):
            qty_open = _safe_float(gr, "qty_open", default=0.0)
            qty = _safe_float(gr, "qty", default=0.0)
            qty_snapshot = qty_open if qty_open > 0.0 else qty

            f.execute("""
                UPDATE follower
                SET status='follow',
                    step=?,
                    req_step=CASE
                        WHEN done_step IS NULL THEN req_step
                        ELSE done_step
                    END,
                    qty_open_snapshot=?,
                    reason='PARTIAL_DONE_ACK',
                    last_action_ts=?
                WHERE uid=?
            """, (g_step, qty_snapshot, now, uid))
            continue

        if req_step != done_step:
            continue

        # Transitions gérées ailleurs (fsm_guard / fsm_status)
        # Rien à faire ici pour l’instant
