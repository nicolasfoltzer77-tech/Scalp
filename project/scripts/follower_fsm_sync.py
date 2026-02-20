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

        if req_step != done_step:
            continue

        # Transitions gérées ailleurs (fsm_guard / fsm_status)
        # Rien à faire ici pour l’instant

