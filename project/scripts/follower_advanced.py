#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FOLLOWER — ACTIONS AVANCÉES
PARTIAL / PYRAMIDE
"""

def advanced_actions(f, e, CFG, now):

    for fr in f.execute("""
        SELECT *
        FROM follower
        WHERE status='follow'
    """):
        uid = fr["uid"]

        pos = e.execute("""
            SELECT qty_open
            FROM v_exec_position
            WHERE uid=?
        """, (uid,)).fetchone()

        if not pos or float(pos["qty_open"] or 0) <= 0:
            continue

        qty_open = float(pos["qty_open"])

        mfe_atr = fr["mfe_atr"]
        mae_atr = fr["mae_atr"]

        # ====================================================
        # TP PARTIAL (SAFE)
        # ====================================================
        if (
            fr["nb_partial"] == 0
            and mfe_atr is not None
            and mfe_atr >= CFG["partial_atr_trigger"]
        ):
            qty = qty_open * CFG["partial_qty_ratio"]

            f.execute("""
                UPDATE follower
                SET status='partial_req',
                    step=step+1,
                    qty_to_close=?,
                    nb_partial=1,
                    last_decision_ts=?,
                    reason='TP_PARTIAL'
                WHERE uid=?
            """, (qty, now, uid))
            continue

        # ====================================================
        # PYRAMIDE (SAFE)
        # ====================================================
        if (
            fr["nb_partial"] >= 1
            and fr["nb_pyramide"] < CFG["max_pyramide_post_partial"]
            and mfe_atr is not None
            and mfe_atr >= CFG["pyramide_atr_trigger"]
            and (
                fr["cooldown_pyramide_ts"] is None
                or now - fr["cooldown_pyramide_ts"] >= CFG["pyramide_cooldown_s"] * 1000
            )
            and (mae_atr is None or mae_atr < CFG["min_mae_forbid_pyramide"])
        ):
            qty = qty_open * CFG["pyramide_qty_ratio"]

            f.execute("""
                UPDATE follower
                SET status='pyramide_req',
                    step=step+1,
                    qty_to_close=?,
                    nb_pyramide=nb_pyramide+1,
                    cooldown_pyramide_ts=?,
                    last_decision_ts=?,
                    reason='PYRAMIDE'
                WHERE uid=?
            """, (qty, now, now, uid))
            continue

