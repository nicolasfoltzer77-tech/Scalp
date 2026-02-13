#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FOLLOWER — FSM SYNC STRICT CANONIQUE

RÈGLES :

1) close_done  → purge follower
2) *_req ACK   → *_stdby (même step)
3) *_done      → retour follow + step = g_step
   CONDITION STRICTE :
       g_step == f_step + 1

INVARIANTS :
- follower.step ne bouge QUE sur *_done
- aucune transition permissive
- aucune régression de step possible
"""

def sync_fsm_status(g, f, now):

    # --------------------------------------------------
    # 1) PURGE CLOSE_DONE
    # --------------------------------------------------
    for r in g.execute("SELECT uid FROM gest WHERE status='close_done'"):
        f.execute("DELETE FROM follower WHERE uid=?", (r["uid"],))


    # --------------------------------------------------
    # 2) SYNC FSM
    # --------------------------------------------------
    rows = f.execute("""
        SELECT uid, status, step
        FROM follower
    """).fetchall()

    for fr in rows:

        uid       = fr["uid"]
        f_status  = fr["status"]
        f_step    = fr["step"] or 0

        gr = g.execute("""
            SELECT status, step
            FROM gest
            WHERE uid=?
        """, (uid,)).fetchone()

        if not gr:
            continue

        g_status = gr["status"]
        g_step   = gr["step"] or 0


        # --------------------------------------------------
        # 2.A) ACK *_req → *_stdby (même step)
        # --------------------------------------------------
        if (
            f_status.endswith("_req")
            and g_status == f_status
            and g_step == f_step
        ):
            f.execute("""
                UPDATE follower
                SET status=?,
                    ts_decision=?
                WHERE uid=?
            """, (f_status.replace("_req", "_stdby"), now, uid))
            continue


        # --------------------------------------------------
        # 2.B) DONE → retour follow + incrément step
        # CONDITION CANONIQUE :
        # g_step == f_step + 1
        # --------------------------------------------------
        if (
            g_status.endswith("_done")
            and g_step == f_step + 1
        ):
            f.execute("""
                UPDATE follower
                SET status='follow',
                    step=?,
                    done_step=?,
                    ts_decision=?
                WHERE uid=?
            """, (g_step, g_step, now, uid))
            continue


