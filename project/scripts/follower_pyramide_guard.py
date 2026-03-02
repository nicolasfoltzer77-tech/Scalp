#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FOLLOWER — PYRAMIDE FSM GUARD
Rôle :
- empêcher les blocages pyramide_req
- synchroniser follower <-> gest
- 🔒 garde-fou pyramide avancée (BTC / ETH uniquement)
"""

# ------------------------------------------------------------
# Instruments autorisés pour pyramide >= 3 (step >= 4)
# ------------------------------------------------------------
ALLOWED_DEEP_PYRAMIDE = {
    "BTC/USDT",
    "ETH/USDT",
}


def guard_pyramide_fsm(*, g, f, now):
    """
    API CANONIQUE — NE JAMAIS MODIFIER LA SIGNATURE

    g   : sqlite gest (READ)
    f   : sqlite follower (WRITE)
    now : timestamp ms
    """

    # Tous les followers bloqués en pyramide_req
    rows = f.execute("""
        SELECT uid, step, instId
        FROM follower
        WHERE status='pyramide_req'
    """).fetchall()

    for fr in rows:
        uid    = fr["uid"]
        step   = fr["step"]
        instId = fr["instId"]

        # --------------------------------------------------------
        # 🔒 GARDE-FOU PYRAMIDE AVANCÉE
        # step:
        # 2 = pyramide 1
        # 3 = pyramide 2
        # 4 = pyramide 3  ❌ sauf BTC / ETH
        # --------------------------------------------------------
        if step >= 4 and instId not in ALLOWED_DEEP_PYRAMIDE:
            # Refus silencieux, FSM safe
            f.execute("""
                UPDATE follower
                SET status='follow',
                    last_action_ts=?
                WHERE uid=? AND status='pyramide_req'
            """, (now, uid))
            continue

        # --------------------------------------------------------
        # SYNCHRO AVEC GEST
        # --------------------------------------------------------
        gr = g.execute("""
            SELECT status, step
            FROM gest
            WHERE uid=?
        """, (uid,)).fetchone()

        if not gr:
            continue

        g_status = gr["status"]
        g_step   = gr["step"]

        # --- PYRAMIDE ACCEPTÉE ---
        # IMPORTANT:
        # gest.step peut diverger temporairement de follower.step selon
        # l'ordre d'ingestion (opener/exec/mirror). Dès que gest confirme
        # pyramide_done, on doit débloquer follower pour reprendre en follow.
        if g_status == "pyramide_done":
            f.execute("""
                UPDATE follower
                SET status='follow',
                    step=COALESCE(?, step),
                    last_action_ts=?
                WHERE uid=? AND status='pyramide_req'
            """, (g_step, now, uid))

        # --- PYRAMIDE REFUSÉE / DÉSYNCHRO ---
        elif g_status not in ("pyramide_req", "pyramide_done"):
            f.execute("""
                UPDATE follower
                SET status='follow',
                    last_action_ts=?
                WHERE uid=? AND status='pyramide_req'
            """, (now, uid))
