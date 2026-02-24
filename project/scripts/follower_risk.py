#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import sqlite3
from pathlib import Path

log = logging.getLogger("FOLLOWER_RISK")


ROOT = Path("/opt/scalp/project")
DB_EXEC = ROOT / "data/exec.db"


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


def _get_exec_price_open(uid):
    """
    Canonical fallback source for avg open price: exec.v_exec_position.
    """
    try:
        with sqlite3.connect(str(DB_EXEC), timeout=2) as e:
            e.row_factory = sqlite3.Row
            row = e.execute(
                """
                SELECT avg_price_open, last_price_exec
                FROM v_exec_position
                WHERE uid=?
                """,
                (uid,)
            ).fetchone()
    except Exception:
        log.exception("[RISK] exec lookup failed uid=%s", uid)
        return None

    if not row:
        return None

    p = _row_get(row, "avg_price_open")
    if p is not None and float(p) > 0.0:
        return float(p)

    last_px = _row_get(row, "last_price_exec")
    if last_px is not None and float(last_px) > 0.0:
        log.warning("[RISK] avg_price_open missing in exec, fallback last_price_exec uid=%s", uid)
        return float(last_px)

    return None


def _resolve_price_open(f, fr):
    """
    Resolve open price with additive fallbacks:
    1) row.avg_price_open (already materialized on follower row)
    2) exec.v_exec_position.avg_price_open (canonical source)
    3) row.last_price_exec (best-effort)
    """
    p = _get_price_open(fr)
    if p is not None and p > 0.0:
        return p

    p_exec = _get_exec_price_open(fr["uid"])
    if p_exec is not None:
        return p_exec

    p4 = _row_get(fr, "last_price_exec")
    if p4 is not None and float(p4) > 0.0:
        log.warning("[RISK] avg_price_open missing, row fallback last_price_exec uid=%s", fr["uid"])
        return float(p4)

    log.warning("[RISK] no price_open source uid=%s", fr["uid"])
    return None


def _resolve_hard_sl_anchor_price(f, fr):
    """
    Hard SL must be anchored on the real executed average entry price.

    Priority:
    1) exec/follower avg open price resolution (_resolve_price_open)
    2) row.entry as last-resort fallback only
    """
    p_exec = _resolve_price_open(f, fr)
    if p_exec is not None and p_exec > 0.0:
        return p_exec

    entry = _row_get(fr, "entry")
    if entry is not None:
        try:
            entry = float(entry)
            if entry > 0.0:
                log.warning("[RISK] hard_sl fallback to row.entry uid=%s", fr["uid"])
                return entry
        except Exception:
            pass

    return None


def _price_from_row(fr):
    p = _row_get(fr, "last_price_exec")
    if p is None:
        return None
    p = float(p)
    return p if p > 0.0 else None


def _norm_side(raw_side):
    """
    Normalize side labels coming from multiple upstream producers.
    Accepted aliases:
      - buy side:  buy / long / b
      - sell side: sell / short / s
    """
    s = (str(raw_side or "").strip().lower())
    if s in ("buy", "long", "b"):
        return "buy"
    if s in ("sell", "short", "s"):
        return "sell"
    return s


def _side_sign(side):
    return 1.0 if side == "buy" else -1.0


def _resolve_atr(fr):
    """
    Follower rows expose `atr_signal` (repo schema), not `atr`.
    Keep a backward-compatible fallback on `atr` if present in legacy views.
    """
    atr = _row_get(fr, "atr_signal")
    if atr in (None, ""):
        atr = _row_get(fr, "atr", 0.0)
    try:
        return float(atr or 0.0)
    except Exception:
        return 0.0


def _resolve_positive_atr(fr):
    atr = _resolve_atr(fr)
    return atr if atr > 0.0 else None


def _set_level_once(f, uid, col, value, now):
    f.execute(f"""
        UPDATE follower
        SET {col}=?,
            last_action_ts=?
        WHERE uid=?
          AND COALESCE({col},0)=0
    """, (value, now, uid))


def _is_near_level(price, level, price_open, ratio):
    if ratio <= 0:
        return False
    base_dist = abs(float(price_open) - float(level))
    if base_dist <= 0:
        return False
    return abs(float(price) - float(level)) <= (base_dist * ratio)


def _recalc_level_50(f, uid, col, old_level, price, now):
    new_level = (float(old_level) + float(price)) * 0.5
    f.execute(f"""
        UPDATE follower
        SET {col}=?,
            last_action_ts=?
        WHERE uid=?
    """, (new_level, now, uid))
    log.info("[LEVEL_50] uid=%s level=%s old=%.6f new=%.6f px=%.6f", uid, col, old_level, new_level, price)


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

    price_open = _resolve_price_open(f, fr)
    if price_open is None:
        return

    # Break-even must lock at real average entry price.
    sl = price_open

    _set_level_once(f, fr["uid"], "sl_be", sl, now)
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

    price_open = _resolve_price_open(f, fr)
    if price_open is None:
        return

    side = _norm_side(_row_get(fr, "side"))
    atr = _resolve_positive_atr(fr)
    if atr is None:
        log.warning("[RISK] skip trail arm (atr<=0) uid=%s", fr["uid"])
        return

    # Trail is anchored from current market price (if available), otherwise open.
    # buy  -> below market ; sell -> above market.
    px = _price_from_row(fr) or price_open
    sign = _side_sign(side)
    sl = px - (sign * atr)

    _set_level_once(f, fr["uid"], "sl_trail", sl, now)
    log.info("[TRAIL_ARMED] uid=%s sl_trail=%.6f", fr["uid"], sl)


def arm_hard_sl(f, fr, CFG, now):
    sl_hard = _row_get(fr, "sl_hard")
    if sl_hard not in (None, 0, 0.0):
        return

    anchor_price = _resolve_hard_sl_anchor_price(f, fr)
    if anchor_price is None:
        return

    side = _norm_side(_row_get(fr, "side"))
    atr = _resolve_positive_atr(fr)
    if atr is None:
        log.warning("[RISK] skip hard sl arm (atr<=0) uid=%s", fr["uid"])
        return
    sign = _side_sign(side)
    sl = anchor_price - (sign * atr)
    _set_level_once(f, fr["uid"], "sl_hard", sl, now)
    log.info("[HARD_SL_ARMED] uid=%s sl_hard=%.6f", fr["uid"], sl)


def enforce_hard_sl_side(f, fr, CFG, now):
    """
    Hard SL invariant:
      - buy  => hard SL must stay BELOW entry/open price
      - sell => hard SL must stay ABOVE entry/open price

    If legacy/rebalanced data breaks this invariant, reset hard SL to its
    canonical ATR-based level.
    """
    sl_hard = _row_get(fr, "sl_hard")
    if sl_hard in (None, 0, 0.0):
        return

    anchor_price = _resolve_hard_sl_anchor_price(f, fr)
    if anchor_price is None:
        return

    side = _norm_side(_row_get(fr, "side"))
    atr = _resolve_atr(fr)
    sign = _side_sign(side)

    # Canonical side-aware hard SL (same formula as arm_hard_sl)
    canonical_sl = anchor_price - (sign * atr)

    wrong_side = ((side == "buy" and float(sl_hard) >= float(anchor_price))
                  or (side == "sell" and float(sl_hard) <= float(anchor_price)))

    if wrong_side:
        f.execute("""
            UPDATE follower
            SET sl_hard=?,
                last_action_ts=?
            WHERE uid=?
        """, (canonical_sl, now, fr["uid"]))
        log.warning(
            "[HARD_SL_FIX] uid=%s side=%s sl_hard=%.6f anchor=%.6f -> %.6f",
            fr["uid"], side, float(sl_hard), float(anchor_price), float(canonical_sl)
        )


def arm_take_profit(f, fr, CFG, now):
    tp = _row_get(fr, "tp_dyn")
    if tp not in (None, 0, 0.0):
        return

    mfe_atr = float(_row_get(fr, "mfe_atr", 0.0) or 0.0)
    trigger = float(CFG.get("tp_dyn_atr_trigger", CFG.get("partial_mfe_atr", 1.0)) or 1.0)
    if mfe_atr < trigger:
        return

    price_open = _resolve_price_open(f, fr)
    if price_open is None:
        return

    side = _norm_side(_row_get(fr, "side"))
    atr = _resolve_positive_atr(fr)
    if atr is None:
        log.warning("[RISK] skip tp arm (atr<=0) uid=%s", fr["uid"])
        return
    sign = _side_sign(side)
    tp = price_open + (sign * atr)
    _set_level_once(f, fr["uid"], "tp_dyn", tp, now)
    log.info("[TP_ARMED] uid=%s tp_dyn=%.6f", fr["uid"], tp)


def rebalance_levels_50(f, fr, CFG, now):
    price = _price_from_row(fr)
    if price is None:
        return

    price_open = _resolve_price_open(f, fr)
    if price_open is None:
        return

    near_ratio = float(CFG.get("risk_near_ratio", 0.25) or 0.25)

    # IMPORTANT: hard SL is immutable after arming (only one-time at open).
    # Rebalance applies only to dynamic levels.
    for col in ("sl_be", "sl_trail", "tp_dyn"):
        level = _row_get(fr, col)
        if level in (None, 0, 0.0):
            continue
        if _is_near_level(price, float(level), price_open, near_ratio):
            _recalc_level_50(f, fr["uid"], col, float(level), price, now)


# ==========================================================
# ENTRY
# ==========================================================
def manage_risk(f, fr, CFG, now):
    arm_hard_sl(f, fr, CFG, now)
    enforce_hard_sl_side(f, fr, CFG, now)
    arm_break_even(f, fr, CFG, now)
    arm_trailing(f, fr, CFG, now)
    arm_take_profit(f, fr, CFG, now)
    rebalance_levels_50(f, fr, CFG, now)
