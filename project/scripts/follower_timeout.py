#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FOLLOWER — TIMEOUT LOGIC
API FIGÉE — NE JAMAIS MODIFIER LA SIGNATURE
"""

def apply_timeouts(*, f, fr, qty_open, age_s, CFG, now):
    """
    f        : sqlite cursor follower
    fr       : row follower
    qty_open : taille réelle ouverte (SOURCE exec.db)
    age_s    : âge en secondes
    CFG      : config follower
    now      : timestamp ms
    """

    uid  = fr["uid"]
    step = int(fr["step"] or 0)

    # --------------------------------------------------
    # HARD TIMEOUT GLOBAL
    # --------------------------------------------------
    if age_s >= CFG["max_trade_age_s"]:
        f.execute("""
            UPDATE follower
            SET status='close_req',
                reason='TIMEOUT_MAX_AGE',
                qty_to_close=?,
                close_step=?,
                last_action_ts=?
            WHERE uid=? AND status='follow'
        """, (qty_open, step, now, uid))
        return

    # --------------------------------------------------
    # NO-MFE TIMEOUT
    # --------------------------------------------------
    if (
        fr["mfe_atr"] < CFG["min_mfe_keep_atr"]
        and age_s >= CFG["max_no_mfe_age_s"]
    ):
        f.execute("""
            UPDATE follower
            SET status='close_req',
                reason='TIMEOUT_NO_MFE',
                qty_to_close=?,
                close_step=?,
                last_action_ts=?
            WHERE uid=? AND status='follow'
        """, (qty_open, step, now, uid))
        return

