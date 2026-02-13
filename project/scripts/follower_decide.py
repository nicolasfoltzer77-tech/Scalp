#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from follower_decide_guard import is_valid_position

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

        # ==========================================================
        # PARTIAL — FILTRE TRADABILITÉ
        # ==========================================================
        if fr["mfe_atr"] >= CFG["partial_mfe_atr"] and fr["nb_partial"] == 0:

            ratio_cfg = CFG["partial_close_ratio"]

            # 🔥 qty_open désormais matérialisé dans follower
            qty_open = float(fr["qty_open"] or 0.0)

            if qty_open <= 0:
                continue

            min_qty = CFG.get("min_partial_qty", 0.0)
            ratio_min_exec = (min_qty / qty_open) if qty_open > 0 else 999.0

            # ------------------------------------------------------
            # 🚫 PARTIAL IMPOSSIBLE
            # ------------------------------------------------------
            if ratio_min_exec > ratio_cfg:
                f.execute("""
                    UPDATE follower
                    SET nb_partial = nb_partial + 1,
                        cooldown_partial_ts=?,
                        ts_decision=?
                    WHERE uid=?
                """, (now, now, uid))
                continue

            # ------------------------------------------------------
            # ✅ PARTIAL VALIDE
            # ------------------------------------------------------
            f.execute("""
                UPDATE follower
                SET status='partial_req',
                    qty_to_close_ratio=?,
                    ratio_to_close=?,
                    req_step=req_step+1,
                    ts_decision=?,
                    nb_partial=1
                WHERE uid=?
            """, (ratio_cfg, ratio_cfg, now, uid))

            continue

