#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FOLLOWER — ACTIONS AVANCÉES
PARTIAL / PYRAMIDE

NOTE:
- Ce module peut être utilisé par certains démons historiques.
- Les règles Option 3 (SAFE_BUILD) sont ajoutées de manière additive.
"""

import logging

log = logging.getLogger("FOLLOWER_ADVANCED")

def _opt3(CFG):
    o = CFG.get("option3_safe_build", {}) or {}
    if not isinstance(o, dict):
        return {}
    return o

def _enabled(CFG):
    return bool(_opt3(CFG).get("enable", False))

def _safe_armed(fr, CFG):
    o = _opt3(CFG)
    allow_be = bool(o.get("allow_after_be", True))
    allow_tr = bool(o.get("allow_after_trail", True))

    sl_be = fr["sl_be"] if "sl_be" in fr.keys() else 0
    sl_tr = fr["sl_trail"] if "sl_trail" in fr.keys() else 0

    be_armed = (sl_be is not None and float(sl_be) > 0.0)
    tr_armed = (sl_tr is not None and float(sl_tr) > 0.0)

    return (allow_be and be_armed) or (allow_tr and tr_armed)

def _add_ratio(CFG, nb_pyr):
    o = _opt3(CFG)
    sizes = o.get("add_sizes", None)
    if isinstance(sizes, list) and 0 <= nb_pyr < len(sizes):
        try:
            return float(sizes[nb_pyr])
        except Exception:
            pass
    return float(CFG.get("pyramide_qty_ratio", 0.0) or 0.0)

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
        # OPTION 3 — PYRAMIDE POST BE/TRAIL (PRIORITAIRE)
        # ====================================================
        if _enabled(CFG):
            o = _opt3(CFG)

            # gate safe armed
            if _safe_armed(fr, CFG):

                # block after partial (default)
                allow_after_partial = bool(o.get("allow_after_partial", False))
                if int(fr["nb_partial"] or 0) >= 1 and not allow_after_partial:
                    pass
                else:
                    max_adds = int(o.get("max_adds_total", 2))
                    nb_pyr = int(fr["nb_pyramide"] or 0)

                    if nb_pyr < max_adds and mfe_atr is not None:

                        min_mae_forbid = float(CFG.get("min_mae_forbid_pyramide", 1e9) or 1e9)
                        if mae_atr is None or float(mae_atr) < min_mae_forbid:

                            cooldown_s = float(o.get("cooldown_s", CFG.get("pyramide_cooldown_s", 0.0)) or 0.0)
                            cd_ts = fr["cooldown_pyramide_ts"]
                            if cd_ts is None or (now - int(cd_ts) >= int(cooldown_s * 1000)):

                                base = float(CFG.get("pyramide_atr_trigger", 0.0) or 0.0)
                                add_step = float(o.get("add_atr_step", 0.0) or 0.0)
                                required = base + nb_pyr * add_step

                                if float(mfe_atr) >= required:

                                    ratio = _add_ratio(CFG, nb_pyr)
                                    if ratio > 0:
                                        # Request pyramide
                                        f.execute("""
                                            UPDATE follower
                                            SET status='pyramide_req',
                                                step=step+1,
                                                qty_to_add_ratio=?,
                                                ratio_to_add=?,
                                                nb_pyramide=nb_pyramide+1,
                                                cooldown_pyramide_ts=?,
                                                last_decision_ts=?,
                                                last_pyramide_ts=?,
                                                last_pyramide_mfe_atr=?,
                                                reason='PYRAMIDE_SAFE_BUILD'
                                            WHERE uid=?
                                        """, (ratio, ratio, now, now, now, float(mfe_atr or 0.0), uid))

                                        if o.get("log_why", False):
                                            log.info("[OPT3] PYRAMIDE uid=%s ratio=%.4f mfe_atr=%.4f", uid, ratio, float(mfe_atr or 0.0))
                                        continue
                            else:
                                if o.get("log_why", False):
                                    log.info("[OPT3] PYRAMIDE_BLOCKED uid=%s why=cooldown", uid)
                        else:
                            if o.get("log_why", False):
                                log.info("[OPT3] PYRAMIDE_BLOCKED uid=%s why=mae_forbid mae_atr=%s", uid, mae_atr)
                    else:
                        if o.get("log_why", False):
                            log.info("[OPT3] PYRAMIDE_BLOCKED uid=%s why=max_adds_or_no_mfe nb_pyr=%s mfe_atr=%s", uid, fr["nb_pyramide"], mfe_atr)
            else:
                if _opt3(CFG).get("log_why", False):
                    log.info("[OPT3] PYRAMIDE_BLOCKED uid=%s why=not_safe_armed", uid)

        # ====================================================
        # TP PARTIAL (SAFE) — legacy
        # ====================================================
        # Option 3: partial only after last add
        if _enabled(CFG) and bool(_opt3(CFG).get("partial_only_after_last_add", True)):
            max_adds = int(_opt3(CFG).get("max_adds_total", 2))
            if int(fr["nb_pyramide"] or 0) < max_adds:
                continue

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
                    last_partial_ts=?,
                    last_partial_mfe_atr=?,
                    reason='TP_PARTIAL'
                WHERE uid=?
            """, (qty, now, now, float(mfe_atr or 0.0), uid))
            continue
