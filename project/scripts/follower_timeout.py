#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FOLLOWER TIMEOUTS

RÈGLE :
- Grace period post-open : 5s
- Aucun timeout ne s’applique tant que la position
  n’a pas vécu au moins 5 secondes en follow.
"""

import time
import logging

log = logging.getLogger("FOLLOWER_TIMEOUT")

GRACE_OPEN_MS = 5000  # 5 secondes


def check_timeouts(CFG):
    """
    Timeout engine.
    """

    from sqlite3 import connect
    from pathlib import Path

    ROOT = Path("/opt/scalp/project")
    DB = ROOT / "data/follower.db"

    now = int(time.time() * 1000)

    f = connect(str(DB))
    f.row_factory = lambda c, r: {col[0]: r[i] for i, col in enumerate(c.description)}

    try:
        rows = f.execute("""
            SELECT *
            FROM follower
            WHERE status = 'follow'
        """).fetchall()

        for fr in rows:
            uid = fr["uid"]

            # ==================================================
            # GRACE PERIOD POST OPEN
            # ==================================================
            ts = fr.get("last_transition_ts") or fr.get("ts_open")
            if ts is not None:
                try:
                    if now - int(ts) < GRACE_OPEN_MS:
                        continue
                except Exception:
                    pass

            # ==================================================
            # TIMEOUTS CLASSIQUES
            # ==================================================

            mfe_atr = float(fr.get("mfe_atr") or 0.0)
            age_s = (now - int(fr.get("ts_open") or now)) / 1000.0

            # --- HARD MAX AGE ---
            max_trade_age_s = CFG.get("max_trade_age_s", 0)
            if max_trade_age_s and age_s > max_trade_age_s:
                f.execute("""
                    UPDATE follower
                    SET status='close_req',
                        reason='TIMEOUT_MAX_AGE'
                    WHERE uid=?
                """, (uid,))
                log.info("[TIMEOUT] close_req uid=%s reason=MAX_AGE", uid)
                continue

            # --- NO MFE ---
            if mfe_atr < CFG.get("min_mfe_keep_atr", 0.0):
                if age_s > CFG.get("max_no_mfe_age_s", 0):
                    f.execute("""
                        UPDATE follower
                        SET status='close_req',
                            reason='TIMEOUT_NO_MFE'
                        WHERE uid=?
                    """, (uid,))
                    log.info("[TIMEOUT] close_req uid=%s reason=NO_MFE", uid)
                    continue

            # --- NO MOVE ---
            if fr.get("mae_atr") is not None:
                if abs(float(fr["mae_atr"])) < CFG.get("timeout_no_move_atr", 0.0):
                    if age_s > CFG.get("timeout_no_move_s", 0):
                        f.execute("""
                            UPDATE follower
                            SET status='close_req',
                                reason='TIMEOUT_NO_MOVE'
                            WHERE uid=?
                        """, (uid,))
                        log.info("[TIMEOUT] close_req uid=%s reason=NO_MOVE", uid)
                        continue

            # --- DRAWDOWN ---
            if fr.get("mae_atr") is not None:
                if abs(float(fr["mae_atr"])) > CFG.get("timeout_drawdown_atr", 0.0):
                    if age_s > CFG.get("timeout_drawdown_s", 0):
                        f.execute("""
                            UPDATE follower
                            SET status='close_req',
                                reason='TIMEOUT_DRAWDOWN'
                        WHERE uid=?
                        """, (uid,))
                        log.info("[TIMEOUT] close_req uid=%s reason=DRAWDOWN", uid)
                        continue

        f.commit()

    finally:
        f.close()
