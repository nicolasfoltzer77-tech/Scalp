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


def sync_fsm_status(g, f, now):
    """
    g : connection gest.db (read)
    f : connection follower.db (write)
    now : timestamp ms
    """

    rows = f.execute("""
        SELECT *
        FROM follower
    """).fetchall()

    for fr in rows:
        uid = fr["uid"]
        status = fr["status"]
        step = fr["step"]

        gr = g.execute("""
            SELECT status, step, qty, qty_open
            FROM gest
            WHERE uid=?
        """, (uid,)).fetchone()

        if not gr:
            continue

        g_status = gr["status"]
        g_step = int(gr["step"] or 0)

        # ==================================================
        # CAS OPEN INITIAL — PRIORITAIRE, SANS AUCUNE CONDITION
        # ==================================================
        if status == "open_stdby" and step == 0:
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
        req_step = fr["req_step"]
        done_step = fr["done_step"]

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
        if status == "pyramide_req" and g_status in DONE_ALIASES:
            qty_snapshot = float(
                gr["qty_open"]
                if gr["qty_open"] is not None
                else (gr["qty"] if gr["qty"] is not None else 0.0)
            )

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
        if g_status == "partial_done" and status == "partial_req":
            qty_snapshot = float(
                gr["qty_open"]
                if gr["qty_open"] is not None
                else (gr["qty"] if gr["qty"] is not None else 0.0)
            )

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
