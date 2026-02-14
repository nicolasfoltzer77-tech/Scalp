#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FOLLOWER — ARMEMENT DES NIVEAUX
SL_BE / SL_TRAIL / TP_DYN

CORRECTION CRITIQUE :
- sl_be / sl_trail sont stockés en DB avec DEFAULT 0.0
- 0.0 doit être traité comme "NON ARMÉ"
- ancien code testait uniquement `is None` → BE jamais armé
"""

def arm_levels(f, g, CFG):

    for r in g.execute("""
        SELECT uid, side, entry
        FROM gest
        WHERE status='follow'
    """):

        fr = f.execute(
            "SELECT * FROM follower WHERE uid=?",
            (r["uid"],)
        ).fetchone()

        if not fr:
            continue

        mfe_atr = fr["mfe_atr"]
        if mfe_atr is None:
            continue

        sl_be    = fr["sl_be"]
        sl_trail = fr["sl_trail"]
        tp_dyn   = fr["tp_dyn"]

        # ======================================================
        # SL BE — ARMEMENT
        # CONDITION CORRIGÉE : None OU <= 0.0 = NON ARMÉ
        # ======================================================
        if (sl_be is None or float(sl_be) <= 0.0) and mfe_atr >= CFG["sl_be_atr_trigger"]:
            sl_be = r["entry"]

        # ======================================================
        # SL TRAIL
        # ======================================================
        if (sl_trail is None or float(sl_trail) <= 0.0) and mfe_atr >= CFG["sl_trail_atr_trigger"]:
            off = CFG["sl_trail_offset_atr"] * fr["atr_signal"]
            sl_trail = (
                r["entry"] - off
                if r["side"] == "sell"
                else r["entry"] + off
            )

        # ======================================================
        # TP DYNAMIQUE
        # ======================================================
        if tp_dyn is None and mfe_atr >= CFG["tp_dyn_atr_trigger"]:
            mul = CFG["tp_dyn_atr_mult"] * fr["atr_signal"]
            tp_dyn = (
                r["entry"] - mul
                if r["side"] == "sell"
                else r["entry"] + mul
            )

        # ======================================================
        # UPDATE DB
        # ======================================================
        f.execute("""
            UPDATE follower
            SET sl_be=?, sl_trail=?, tp_dyn=?
            WHERE uid=?
        """, (sl_be, sl_trail, tp_dyn, r["uid"]))
