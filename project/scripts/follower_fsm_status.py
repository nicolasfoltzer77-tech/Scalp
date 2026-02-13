#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FOLLOWER FSM STATUS SYNC
- Pas de *_stdby côté follower
- Reset follow UNIQUEMENT après gest.*_done
- Purge follower sur gest.close_done
"""

def sync_fsm_status(g, f, now):
    """
    g : connexion gest.db
    f : connexion follower.db
    """

    for fr in f.execute("SELECT uid, status, step FROM follower"):
        uid      = fr["uid"]
        f_status = fr["status"]
        f_step   = fr["step"]

        gr = g.execute(
            "SELECT status, step FROM gest WHERE uid=?",
            (uid,)
        ).fetchone()

        # --------------------------------------------
        # UID orphelin → purge (NO_GEST)
        # --------------------------------------------
        if not gr:
            f.execute("DELETE FROM follower WHERE uid=?", (uid,))
            continue

        g_status = gr["status"]
        g_step   = gr["step"]

        # --------------------------------------------
        # CLOSE_DONE = ÉTAT TERMINAL → PURGE FOLLOWER
        # --------------------------------------------
        if g_status == "close_done":
            f.execute("DELETE FROM follower WHERE uid=?", (uid,))
            continue

        # --------------------------------------------
        # RESET FOLLOWER APRÈS *_DONE (ACK FINAL)
        # --------------------------------------------
        if (
            g_status.endswith("_done")
            and f_step == g_step
            and f_status != "follow"
        ):
            f.execute("""
                UPDATE follower
                SET
                    status='follow',
                    reason='DONE_RESET',
                    last_action_ts=?
                WHERE uid=?
            """, (now, uid))
            continue

        # --------------------------------------------
        # AUCUN *_stdby AUTORISÉ CÔTÉ FOLLOWER
        # --------------------------------------------
        if f_status.endswith("_stdby"):
            f.execute("""
                UPDATE follower
                SET
                    status='follow',
                    reason='FORCED_NO_STDBY',
                    last_action_ts=?
                WHERE uid=?
            """, (now, uid))
            continue

