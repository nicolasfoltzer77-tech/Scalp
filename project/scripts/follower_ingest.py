#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FOLLOWER — INGEST OPEN_DONE
SOURCE UNIQUE : gest.db

RÔLE :
- créer la ligne follower à open_done
- si la ligne existe déjà : synchroniser status/step SANS toucher ts_follow

FIX CANONIQUE (repo) :
- ts_follow DOIT ÊTRE = ts_open (invariant MFE/MAE)
- ne pas régénérer ts_follow avec now
"""

from db_utils import ensure_column


def ingest_open_done(g, f, now):
    """
    g : sqlite gest (READ)
    f : sqlite follower (WRITE)
    now : timestamp ms
    """

    rows = g.execute(
        """
        SELECT
            uid,
            instId,
            side,
            step,
            ts_open,
            entry,
            atr_signal,
            qty,
            lev,
            score_C,
            score_S,
            score_H,
            score_M,
            entry_range_pos,
            entry_distance_atr,
            trigger_strength,
            market_regime
        FROM gest
        WHERE status='open_done'
    """
    ).fetchall()

    for col in ("score_C", "score_S", "score_H", "score_M", "entry_range_pos", "entry_distance_atr", "trigger_strength"):
        ensure_column(f, "follower", col, "REAL")
    ensure_column(f, "follower", "market_regime", "TEXT")

    if not rows:
        return

    for r in rows:
        uid = r["uid"]
        side = str(r["side"] or "").strip().lower()
        entry = float(r["entry"] or 0.0)
        atr_signal = float(r["atr_signal"] or 0.0)

        if side in ("sell", "short", "s"):
            sl_hard = entry + atr_signal
        else:
            sl_hard = entry - atr_signal

        fr = f.execute(
            """
            SELECT uid, ts_follow, step, done_step, side, instId
            FROM follower
            WHERE uid=?
        """,
            (uid,),
        ).fetchone()

        if fr:
            step_in = int(r["step"] or 0)
            step_cur = int(fr["step"] or 0)
            done_cur = int(fr["done_step"] or 0)
            side_cur = str(fr["side"] or "").strip().lower()
            side_in = str(r["side"] or "").strip().lower()
            inst_cur = str(fr["instId"] or "")
            inst_in = str(r["instId"] or "")

            is_new_cycle = step_in < step_cur or done_cur > step_in or side_cur != side_in or inst_cur != inst_in

            if is_new_cycle:
                f.execute(
                    """
                    UPDATE follower
                    SET status='follow',
                        instId=?, side=?, step=?, req_step=?, done_step=?,
                        score_C=?, score_S=?, score_H=?, score_M=?,
                        entry_range_pos=?, entry_distance_atr=?, trigger_strength=?, market_regime=?,
                        atr_signal=?, sl_hard=?,
                        sl_be=0, sl_trail=0, tp_dyn=0,
                        reason=NULL, reason_close=NULL,
                        price_to_close=0, qty_to_close=0, qty_to_close_ratio=0,
                        ratio_to_close=0, qty_to_add_ratio=0, ratio_to_add=NULL,
                        nb_partial=0, nb_pyramide=0, nb_pyramide_ack=0, nb_pyramide_post_partial=0,
                        cooldown_partial_ts=NULL, cooldown_pyramide_ts=NULL,
                        last_partial_ts=NULL, last_pyramide_ts=NULL,
                        first_partial_ts=NULL, first_pyramide_ts=NULL,
                        first_partial_mfe_atr=NULL, last_partial_mfe_atr=NULL, last_pyramide_mfe_atr=NULL,
                        ratio_closed=0, ratio_exposed=0,
                        last_action_ts=?
                    WHERE uid=?
                """,
                    (
                        r["instId"],
                        r["side"],
                        step_in,
                        step_in,
                        step_in,
                        r["score_C"],
                        r["score_S"],
                        r["score_H"],
                        r["score_M"],
                        r["entry_range_pos"],
                        r["entry_distance_atr"],
                        r["trigger_strength"],
                        r["market_regime"],
                        atr_signal,
                        sl_hard,
                        now,
                        uid,
                    ),
                )
                continue

            f.execute(
                """
                UPDATE follower
                SET status='follow',
                    instId=?, side=?, step=?,
                    score_C=COALESCE(?, score_C),
                    score_S=COALESCE(?, score_S),
                    score_H=COALESCE(?, score_H),
                    score_M=COALESCE(?, score_M),
                    entry_range_pos=COALESCE(?, entry_range_pos),
                    entry_distance_atr=COALESCE(?, entry_distance_atr),
                    trigger_strength=COALESCE(?, trigger_strength),
                    market_regime=COALESCE(?, market_regime),
                    req_step=CASE
                        WHEN COALESCE(req_step, 0) < COALESCE(?, 0) THEN COALESCE(?, 0)
                        ELSE req_step
                    END,
                    done_step=CASE
                        WHEN COALESCE(done_step, 0) < COALESCE(?, 0) THEN COALESCE(?, 0)
                        ELSE done_step
                    END,
                    atr_signal=?,
                    sl_hard=CASE WHEN COALESCE(sl_hard, 0)=0 THEN ? ELSE sl_hard END,
                    last_action_ts=?
                WHERE uid=?
            """,
                (
                    r["instId"],
                    r["side"],
                    r["step"] or 0,
                    r["score_C"],
                    r["score_S"],
                    r["score_H"],
                    r["score_M"],
                    r["entry_range_pos"],
                    r["entry_distance_atr"],
                    r["trigger_strength"],
                    r["market_regime"],
                    r["step"] or 0,
                    r["step"] or 0,
                    r["step"] or 0,
                    r["step"] or 0,
                    atr_signal,
                    sl_hard,
                    now,
                    uid,
                ),
            )
            continue

        f.execute(
            """
            INSERT INTO follower (
                uid, instId, side, step, status,
                ts_follow, last_action_ts,
                qty_ratio, nb_partial, nb_pyramide,
                score_C, score_S, score_H, score_M,
                atr_signal, sl_hard,
                req_step, done_step,
                entry_range_pos, entry_distance_atr,
                trigger_strength, market_regime
            ) VALUES (
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
            )
        """,
            (
                uid,
                r["instId"],
                r["side"],
                r["step"] or 0,
                "follow",
                r["ts_open"],
                now,
                1.0,
                0,
                0,
                r["score_C"],
                r["score_S"],
                r["score_H"],
                r["score_M"],
                atr_signal,
                sl_hard,
                r["step"] or 0,
                r["step"] or 0,
                r["entry_range_pos"],
                r["entry_distance_atr"],
                r["trigger_strength"],
                r["market_regime"],
            ),
        )
