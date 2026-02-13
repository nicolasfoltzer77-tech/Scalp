#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FOLLOWER — ARMEMENT DES NIVEAUX
SL_BE / SL_TRAIL / TP_DYN
AUCUNE ACTION
"""

def arm_levels(f, g, CFG):
    for r in g.execute("""
        SELECT uid, side, entry
        FROM gest
        WHERE status='follow'
    """):
        fr = f.execute("SELECT * FROM follower WHERE uid=?", (r["uid"],)).fetchone()
        if not fr:
            continue

        mfe_atr = fr["mfe_atr"]
        if mfe_atr is None:
            continue

        sl_be    = fr["sl_be"]
        sl_trail = fr["sl_trail"]
        tp_dyn   = fr["tp_dyn"]

        if sl_be is None and mfe_atr >= CFG["sl_be_atr_trigger"]:
            sl_be = r["entry"]

        if sl_trail is None and mfe_atr >= CFG["sl_trail_atr_trigger"]:
            off = CFG["sl_trail_offset_atr"] * fr["atr_signal"]
            sl_trail = r["entry"] - off if r["side"] == "sell" else r["entry"] + off

        if tp_dyn is None and mfe_atr >= CFG["tp_dyn_atr_trigger"]:
            mul = CFG["tp_dyn_atr_mult"] * fr["atr_signal"]
            tp_dyn = r["entry"] - mul if r["side"] == "sell" else r["entry"] + mul

        f.execute("""
            UPDATE follower
            SET sl_be=?, sl_trail=?, tp_dyn=?
            WHERE uid=?
        """, (sl_be, sl_trail, tp_dyn, r["uid"]))

