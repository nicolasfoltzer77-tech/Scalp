#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FOLLOWER — ARM LEVELS

- Arm BE / TRAIL
- MFE/MAE read-only from mfe_mae.db (Option B)
- ATTACH performed ONCE per connection
- No cross-DB writes
"""

import logging
import time

log = logging.getLogger("FOLLOWER_ARM")

MFE_DB_PATH = "/opt/scalp/project/data/mfe_mae.db"


def _ensure_mfe_attached(f):
    """
    Attach mfe_mae.db once per connection (idempotent).
    """
    rows = f.execute("PRAGMA database_list").fetchall()
    for r in rows:
        if r["name"] == "mfe":
            return
    f.execute(
        "ATTACH DATABASE ? AS mfe",
        (MFE_DB_PATH,)
    )


def _fetch_mfe_mae(f, uid):
    """
    Read-only SELECT from mfe_mae.v_follow_mfe
    """
    row = f.execute("""
        SELECT mfe_atr, mae_atr
        FROM mfe.v_follow_mfe
        WHERE uid = ?
    """, (uid,)).fetchone()

    if not row:
        return None, None

    return row["mfe_atr"], row["mae_atr"]


def arm_levels(f, g, CFG):
    """
    Arm BE / TRAIL for FOLLOW trades
    """

    # ✅ ATTACH ONCE HERE
    _ensure_mfe_attached(f)

    rows = f.execute("""
        SELECT uid,
               avg_price_open,
               sl_be,
               sl_trail
        FROM follower
        WHERE status='follow'
    """).fetchall()

    if not rows:
        return

    now = int(time.time() * 1000)

    for fr in rows:
        uid = fr["uid"]

        mfe_atr, mae_atr = _fetch_mfe_mae(f, uid)
        if mfe_atr is None:
            continue

        # ==================================================
        # BREAK EVEN — on executed price
        # ==================================================
        if (
            fr["sl_be"] == 0.0
            and mfe_atr >= CFG["sl_be_atr_trigger"]
            and fr["avg_price_open"] > 0.0
        ):
            f.execute("""
                UPDATE follower
                SET sl_be = avg_price_open,
                    last_action_ts = ?
                WHERE uid = ?
                  AND sl_be = 0.0
            """, (
                now,
                uid
            ))

            log.info(
                "[ARM] BE uid=%s mfe_atr=%.4f be=%.8f",
                uid,
                mfe_atr,
                fr["avg_price_open"]
            )

        # ==================================================
        # TRAILING STOP
        # ==================================================
        if (
            fr["sl_trail"] == 0.0
            and mfe_atr >= CFG["sl_trail_atr_trigger"]
            and fr["avg_price_open"] > 0.0
        ):
            f.execute("""
                UPDATE follower
                SET sl_trail = avg_price_open,
                    last_action_ts = ?
                WHERE uid = ?
                  AND sl_trail = 0.0
            """, (
                now,
                uid
            ))

            log.info(
                "[ARM] TRAIL uid=%s mfe_atr=%.4f trail=%.8f",
                uid,
                mfe_atr,
                fr["avg_price_open"]
            )
