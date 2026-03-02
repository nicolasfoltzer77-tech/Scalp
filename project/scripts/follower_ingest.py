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

def ingest_open_done(g, f, now):
    """
    g : sqlite gest (READ)
    f : sqlite follower (WRITE)
    now : timestamp ms
    """

    rows = g.execute("""
        SELECT
            uid,
            instId,
            side,
            step,
            ts_open,
            entry,
            atr_signal,
            qty,
            lev
        FROM gest
        WHERE status='open_done'
    """).fetchall()

    if not rows:
        return

    for r in rows:
        uid = r["uid"]
        side = str(r["side"] or "").strip().lower()
        entry = float(r["entry"] or 0.0)
        atr_signal = float(r["atr_signal"] or 0.0)

        # Hard SL must be initialized directly at ingestion.
        # buy  => entry - ATR ; sell => entry + ATR.
        if side in ("sell", "short", "s"):
            sl_hard = entry + atr_signal
        else:
            sl_hard = entry - atr_signal

        # Existe déjà ?
        fr = f.execute("""
            SELECT
                uid,
                ts_follow,
                step,
                done_step,
                side,
                instId
            FROM follower
            WHERE uid=?
        """, (uid,)).fetchone()

        if fr:
            step_in = int(r["step"] or 0)
            step_cur = int(fr["step"] or 0)
            done_cur = int(fr["done_step"] or 0)
            side_cur = str(fr["side"] or "").strip().lower()
            side_in = str(r["side"] or "").strip().lower()
            inst_cur = str(fr["instId"] or "")
            inst_in = str(r["instId"] or "")

            # Nouveau cycle (UID réutilisé): il faut purger les niveaux dynamiques
            # et les compteurs de fermeture pour éviter des close_req fantômes.
            is_new_cycle = (
                step_in < step_cur
                or done_cur > step_in
                or side_cur != side_in
                or inst_cur != inst_in
            )

            if is_new_cycle:
                f.execute("""
                    UPDATE follower
                    SET status='follow',
                        instId=?,
                        side=?,
                        step=?,
                        req_step=?,
                        done_step=?,
                        atr_signal=?,
                        sl_hard=?,
                        sl_be=0,
                        sl_trail=0,
                        tp_dyn=0,
                        reason=NULL,
                        reason_close=NULL,
                        price_to_close=0,
                        qty_to_close=0,
                        qty_to_close_ratio=0,
                        ratio_to_close=0,
                        qty_to_add_ratio=0,
                        ratio_to_add=NULL,
                        ratio_closed=0,
                        ratio_exposed=0,
                        last_action_ts=?
                    WHERE uid=?
                """, (
                    r["instId"],
                    r["side"],
                    step_in,
                    step_in,
                    step_in,
                    atr_signal,
                    sl_hard,
                    now,
                    uid
                ))
                continue

            # Sync non destructif : ne pas toucher ts_follow (invariant MFE/MAE)
            f.execute("""
                UPDATE follower
                SET status='follow',
                    instId=?,
                    side=?,
                    step=?,
                    req_step=CASE
                        WHEN COALESCE(req_step, 0) < COALESCE(?, 0) THEN COALESCE(?, 0)
                        ELSE req_step
                    END,
                    done_step=CASE
                        WHEN COALESCE(done_step, 0) < COALESCE(?, 0) THEN COALESCE(?, 0)
                        ELSE done_step
                    END,
                    atr_signal=?,
                    sl_hard=CASE
                        WHEN COALESCE(sl_hard, 0)=0 THEN ?
                        ELSE sl_hard
                    END,
                    last_action_ts=?
                WHERE uid=?
            """, (
                r["instId"],
                r["side"],
                r["step"] or 0,
                r["step"] or 0,
                r["step"] or 0,
                r["step"] or 0,
                r["step"] or 0,
                atr_signal,
                sl_hard,
                now,
                uid
            ))
            continue

        # Création canonique : ts_follow = ts_open
        f.execute("""
            INSERT INTO follower (
                uid,
                instId,
                side,
                step,
                status,
                ts_follow,
                last_action_ts,
                qty_ratio,
                nb_partial,
                nb_pyramide,
                atr_signal,
                sl_hard,
                req_step,
                done_step
            ) VALUES (
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?
            )
        """, (
            uid,
            r["instId"],
            r["side"],
            r["step"] or 0,
            "follow",
            r["ts_open"],   # ✅ INVARIANT
            now,
            1.0,
            0,
            0,
            atr_signal,
            sl_hard,
            r["step"] or 0,
            r["step"] or 0
        ))
