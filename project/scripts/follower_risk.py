#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from math import copysign

log = logging.getLogger("FOLLOWER_RISK")


# ==========================================================
# SQLITE ROW SAFE ACCESS
# ==========================================================
def _row_get(fr, key, default=None):
    try:
        return fr[key]
    except Exception:
        return default


def _get_price_open(fr):
    """
    Repo truth:
    - follower does NOT have price_open
    - correct reference is avg_price_open (from v_exec_position)
    """
    p = _row_get(fr, "avg_price_open")
    if p is None:
        log.debug("[RISK] missing avg_price_open uid=%s", fr["uid"])
        return None
    return float(p)


# ==========================================================
# BREAK EVEN
# ==========================================================
def arm_break_even(f, fr, CFG, now):

    sl_be = _row_get(fr, "sl_be")
    if sl_be not in (None, 0, 0.0):
        return

    mfe_atr = float(_row_get(fr, "mfe_atr", 0.0) or 0.0)
    trigger = float(CFG.get("sl_be_atr_trigger", 0.0) or 0.0)
    if mfe_atr < trigger:
        return

    price_open = _get_price_open(fr)
    if price_open is None:
        return

    side = fr["side"]
    atr = float(_row_get(fr, "atr", 0.0) or 0.0)
    offset = float(CFG.get("sl_be_offset_atr", 0.0) or 0.0)

    sl = price_open + copysign(offset * atr, 1 if side == "buy" else -1)

    f.execute("""
        UPDATE follower
        SET sl_be=?,
            step=COALESCE(step,0)+1,
            last_action_ts=?
        WHERE uid=?
          AND COALESCE(sl_be,0)=0
    """, (sl, now, fr["uid"]))
    log.info("[BE_ARMED] uid=%s sl_be=%.6f", fr["uid"], sl)


# ==========================================================
# TRAILING STOP
# ==========================================================
def arm_trailing(f, fr, CFG, now):

    sl_tr = _row_get(fr, "sl_trail")
    if sl_tr not in (None, 0, 0.0):
        return

    mfe_atr = float(_row_get(fr, "mfe_atr", 0.0) or 0.0)
    trigger = float(CFG.get("sl_trail_atr_trigger", 0.0) or 0.0)
    if mfe_atr < trigger:
        return

    price_open = _get_price_open(fr)
    if price_open is None:
        return

    side = fr["side"]
    atr = float(_row_get(fr, "atr", 0.0) or 0.0)
    offset = float(CFG.get("sl_trail_offset_atr", 0.0) or 0.0)

    sl = price_open + copysign(offset * atr, 1 if side == "buy" else -1)

    f.execute("""
        UPDATE follower
        SET sl_trail=?,
            step=COALESCE(step,0)+1,
            last_action_ts=?
        WHERE uid=?
          AND COALESCE(sl_trail,0)=0
    """, (sl, now, fr["uid"]))
    log.info("[TRAIL_ARMED] uid=%s sl_trail=%.6f", fr["uid"], sl)


# ==========================================================
# ENTRY
# ==========================================================
def manage_risk(f, fr, CFG, now):
    arm_break_even(f, fr, CFG, now)
    arm_trailing(f, fr, CFG, now)
