#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from follower_decide_guard import is_valid_position

log = logging.getLogger("FOLLOWER_DECIDE")

def _opt3(CFG):
    o = CFG.get("option3_safe_build", {}) or {}
    if not isinstance(o, dict):
        return {}
    return o

def _is_enabled_opt3(CFG):
    o = _opt3(CFG)
    return bool(o.get("enable", False))

def _is_safe_armed(fr_full, CFG):
    """
    SAFE = BE and/or TRAIL armed (post-BE/trail pyramiding gate).
    follower schema uses defaults 0, so treat >0 as armed.
    """
    o = _opt3(CFG)
    allow_be = bool(o.get("allow_after_be", True))
    allow_tr = bool(o.get("allow_after_trail", True))

    sl_be = fr_full["sl_be"] if "sl_be" in fr_full.keys() else 0
    sl_tr = fr_full["sl_trail"] if "sl_trail" in fr_full.keys() else 0

    be_armed = (sl_be is not None and float(sl_be) > 0.0)
    tr_armed = (sl_tr is not None and float(sl_tr) > 0.0)

    return (allow_be and be_armed) or (allow_tr and tr_armed)

def _get_add_ratio(CFG, nb_pyramide_done):
    o = _opt3(CFG)
    sizes = o.get("add_sizes", None)
    if isinstance(sizes, list) and nb_pyramide_done >= 0 and nb_pyramide_done < len(sizes):
        try:
            return float(sizes[nb_pyramide_done])
        except Exception:
            pass
    # fallback legacy ratio
    return float(CFG.get("pyramide_qty_ratio", 0.0) or 0.0)

def _should_pyramide_opt3(fr_state, fr_full, CFG, now):
    o = _opt3(CFG)

    # kill-switch
    if not _is_enabled_opt3(CFG):
        return (False, "opt3_disabled", None)

    # must be safe-armed (BE or trail) to build
    if not _is_safe_armed(fr_full, CFG):
        return (False, "not_safe_armed", None)

    # block adds after partial unless explicitly allowed
    allow_after_partial = bool(o.get("allow_after_partial", False))
    nb_partial = int(fr_state["nb_partial"] or 0)
    if nb_partial >= 1 and not allow_after_partial:
        return (False, "blocked_after_partial", None)

    # max adds total
    max_adds = int(o.get("max_adds_total", 2))
    nb_pyr = int(fr_state["nb_pyramide"] or 0)
    if nb_pyr >= max_adds:
        return (False, "max_adds_reached", None)

    mfe_atr = fr_state["mfe_atr"]
    if mfe_atr is None:
        return (False, "no_mfe_atr", None)

    mae_atr = fr_state["mae_atr"]
    min_mae_forbid = float(CFG.get("min_mae_forbid_pyramide", 1e9) or 1e9)
    if mae_atr is not None and float(mae_atr) >= min_mae_forbid:
        return (False, "mae_forbid", None)

    # cooldown (ms)
    cooldown_s = float(o.get("cooldown_s", CFG.get("pyramide_cooldown_s", 0.0)) or 0.0)
    cd_ts = fr_full["cooldown_pyramide_ts"] if "cooldown_pyramide_ts" in fr_full.keys() else None
    if cd_ts is not None:
        try:
            if now - int(cd_ts) < int(cooldown_s * 1000):
                return (False, "cooldown", None)
        except Exception:
            pass

    # atr_extension trigger model:
    # required = base + nb_pyr * add_atr_step, with base from CFG["pyramide_atr_trigger"]
    base = float(CFG.get("pyramide_atr_trigger", 0.0) or 0.0)
    add_step = float(o.get("add_atr_step", 0.0) or 0.0)
    required = base + nb_pyr * add_step

    if float(mfe_atr) < required:
        return (False, "mfe_below_required", required)

    ratio = _get_add_ratio(CFG, nb_pyr)
    if ratio <= 0:
        return (False, "add_ratio_zero", ratio)

    return (True, "ok", ratio)

def _should_partial_opt3(fr_state, fr_full, CFG):
    o = _opt3(CFG)
    if not _is_enabled_opt3(CFG):
        return True  # legacy behavior unchanged

    # partial only after last add (validated)
    if bool(o.get("partial_only_after_last_add", True)):
        max_adds = int(o.get("max_adds_total", 2))
        nb_pyr = int(fr_state["nb_pyramide"] or 0)
        if nb_pyr < max_adds:
            return False

    return True

def decide_core(f, CFG, now):

    rows = f.execute("""
        SELECT *
        FROM v_follower_state
        WHERE status='follow'
    """).fetchall()

    for fr in rows:

        if not is_valid_position(fr):
            continue

        uid = fr["uid"]

        fr_full = f.execute("SELECT * FROM follower WHERE uid=?", (uid,)).fetchone()
        if not fr_full:
            continue

        # ==========================================================
        # OPTION 3 — PYRAMIDE PRIORITAIRE (post BE / trail)
        # ==========================================================
        if _is_enabled_opt3(CFG):
            ok, why, ratio_or_req = _should_pyramide_opt3(fr, fr_full, CFG, now)
            if ok:
                ratio_add = float(ratio_or_req)

                # Request pyramide (additive, uses existing columns)
                f.execute("""
                    UPDATE follower
                    SET status='pyramide_req',
                        qty_to_add_ratio=?,
                        ratio_to_add=?,
                        req_step=req_step+1,
                        step=step+1,
                        ts_decision=?,
                        last_decision_ts=?,
                        nb_pyramide=nb_pyramide+1,
                        cooldown_pyramide_ts=?,
                        last_pyramide_ts=?,
                        last_pyramide_mfe_atr=?,
                        reason='PYRAMIDE_SAFE_BUILD'
                    WHERE uid=?
                """, (
                    ratio_add,
                    ratio_add,
                    now,
                    now,
                    now,
                    now,
                    float(fr["mfe_atr"] or 0.0),
                    uid
                ))

                if _opt3(CFG).get("log_why", False):
                    log.info("[OPT3] PYRAMIDE uid=%s ratio=%.4f mfe_atr=%.4f nb_pyr->%d", uid, ratio_add, float(fr["mfe_atr"] or 0.0), int(fr["nb_pyramide"] or 0) + 1)

                continue
            else:
                if _opt3(CFG).get("log_why", False):
                    if ratio_or_req is None:
                        log.info("[OPT3] PYRAMIDE_BLOCKED uid=%s why=%s mfe_atr=%s", uid, why, fr["mfe_atr"])
                    else:
                        log.info("[OPT3] PYRAMIDE_BLOCKED uid=%s why=%s required=%s mfe_atr=%s", uid, why, ratio_or_req, fr["mfe_atr"])

        # ==========================================================
        # PARTIAL — FILTRE TRADABILITÉ
        # ==========================================================
        if fr["mfe_atr"] >= CFG["partial_mfe_atr"] and fr["nb_partial"] == 0:

            # Option 3: partial only after last add
            if not _should_partial_opt3(fr, fr_full, CFG):
                if _opt3(CFG).get("log_why", False):
                    log.info("[OPT3] PARTIAL_BLOCKED uid=%s why=partial_only_after_last_add nb_pyr=%s", uid, fr["nb_pyramide"])
                continue

            ratio_cfg = CFG["partial_close_ratio"]

            # qty_open désormais matérialisé dans follower
            qty_open = float(fr["qty_open"] or 0.0)

            if qty_open <= 0:
                continue

            min_qty = CFG.get("min_partial_qty", 0.0)
            ratio_min_exec = (min_qty / qty_open) if qty_open > 0 else 999.0

            # ------------------------------------------------------
            # PARTIAL IMPOSSIBLE
            # ------------------------------------------------------
            if ratio_min_exec > ratio_cfg:
                f.execute("""
                    UPDATE follower
                    SET nb_partial = nb_partial + 1,
                        cooldown_partial_ts=?,
                        ts_decision=?,
                        last_decision_ts=?,
                        reason='PARTIAL_SKIPPED_MIN_QTY'
                    WHERE uid=?
                """, (now, now, now, uid))
                continue

            # ------------------------------------------------------
            # PARTIAL VALIDE
            # ------------------------------------------------------
            f.execute("""
                UPDATE follower
                SET status='partial_req',
                    qty_to_close_ratio=?,
                    ratio_to_close=?,
                    req_step=req_step+1,
                    step=step+1,
                    ts_decision=?,
                    last_decision_ts=?,
                    nb_partial=1,
                    last_partial_ts=?,
                    last_partial_mfe_atr=?,
                    reason='TP_PARTIAL'
                WHERE uid=?
            """, (
                ratio_cfg,
                ratio_cfg,
                now,
                now,
                now,
                float(fr["mfe_atr"] or 0.0),
                uid
            ))

            continue
