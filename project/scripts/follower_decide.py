#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import sqlite3
from pathlib import Path
from follower_decide_guard import is_valid_position

log = logging.getLogger("FOLLOWER_DECIDE")

ROOT = Path("/opt/scalp/project")
DB_TICKS = ROOT / "data/ticks.db"
DB_T = ROOT / "data/t.db"


def _get_market_price(inst_id):
    """
    Prefer latest market tick over last execution price.
    last_price_exec only changes on fills and is not suitable for SL/TP triggers.
    """
    if not inst_id:
        return None
    candidates = [inst_id, str(inst_id).replace("/", "")]
    for db_path in (DB_TICKS, DB_T):
        try:
            with sqlite3.connect(str(db_path), timeout=1) as t:
                t.row_factory = sqlite3.Row
                for candidate in candidates:
                    row = t.execute(
                        "SELECT lastPr FROM ticks WHERE instId=?",
                        (candidate,),
                    ).fetchone()
                    if row:
                        try:
                            px = float(row["lastPr"])
                        except Exception:
                            px = None
                        if px is not None and px > 0:
                            return px
        except Exception:
            log.debug("[DECIDE] ticks lookup failed db=%s instId=%s", db_path, inst_id, exc_info=True)

    return None


def _stop_hit(side, price_now, level):
    if level is None:
        return False
    try:
        level = float(level)
    except Exception:
        return False
    if level <= 0.0:
        return False

    # Stop convention:
    # - buy  : stop is below market, hit when now <= stop
    # - sell : stop is above market, hit when now >= stop
    if side == "buy":
        return float(price_now) <= level
    if side == "sell":
        return float(price_now) >= level
    return False


def _take_profit_hit(side, price_now, level):
    if level is None:
        return False
    try:
        level = float(level)
    except Exception:
        return False
    if level <= 0.0:
        return False

    if side == "buy":
        return float(price_now) >= level
    if side == "sell":
        return float(price_now) <= level
    return False


def _pyramide_required_mfe_atr(next_step, CFG):
    """
    next_step = 2 for first add, 3 for second add, ...
    Rules:
      step 2 => 0.45 ATR
      step 3 => 0.70 ATR
      step x => pyramide_mfe_base + pyramide_mfe_step * (x-1)
    """
    if next_step <= 1:
        return 0.0
    if next_step == 2:
        return float(CFG.get("pyramide_atr_trigger", 0.45) or 0.45)

    base = float(CFG.get("pyramide_mfe_base", 0.20) or 0.20)
    step = float(CFG.get("pyramide_mfe_step", 0.25) or 0.25)
    return base + step * (next_step - 1)


def _should_pyramide(fr_state, fr_full, CFG, now):
    mfe_atr = fr_state["mfe_atr"]
    if mfe_atr is None:
        return (False, "no_mfe_atr", None)

    mae_atr = fr_state["mae_atr"]
    min_mae_forbid = float(CFG.get("min_mae_forbid_pyramide", 1e9) or 1e9)
    if mae_atr is not None and float(mae_atr) >= min_mae_forbid:
        return (False, "mae_forbid", None)

    max_adds = int(CFG.get("pyramide_max_adds", 5) or 5)
    nb_pyr = int(fr_state["nb_pyramide"] or 0)
    if nb_pyr >= max_adds:
        return (False, "max_adds_reached", None)

    cooldown_s = float(CFG.get("pyramide_cooldown_s", 0.0) or 0.0)
    cd_ts = fr_full["cooldown_pyramide_ts"] if "cooldown_pyramide_ts" in fr_full.keys() else None
    if cd_ts is not None:
        try:
            if now - int(cd_ts) < int(cooldown_s * 1000):
                return (False, "cooldown", None)
        except Exception:
            pass

    next_step = nb_pyr + 2
    required = _pyramide_required_mfe_atr(next_step, CFG)
    if float(mfe_atr) < required:
        return (False, "mfe_below_required", required)

    ratio = float(CFG.get("pyramide_qty_ratio", 0.0) or 0.0)
    if ratio <= 0:
        return (False, "add_ratio_zero", ratio)

    return (True, "ok", ratio)

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

        side = str(fr_full["side"] or "").strip().lower()
        price_now = _get_market_price(fr_full["instId"])
        if price_now is None:
            price_now = fr_full["last_price_exec"]
            if price_now is not None:
                try:
                    price_now = float(price_now)
                except Exception:
                    price_now = None

        if price_now is not None and price_now > 0.0:
            close_reason = None
            if _stop_hit(side, price_now, fr_full["sl_hard"]):
                close_reason = "SL_HARD"
            elif _stop_hit(side, price_now, fr_full["sl_be"]):
                close_reason = "SL_BE"
            elif _stop_hit(side, price_now, fr_full["sl_trail"]):
                close_reason = "SL_TRAIL"
            elif _take_profit_hit(side, price_now, fr_full["tp_dyn"]):
                close_reason = "TP_DYN"

            if close_reason:
                f.execute("""
                    UPDATE follower
                    SET status='close_req',
                        qty_to_close_ratio=1.0,
                        ratio_to_close=1.0,
                        req_step=req_step+1,
                        ts_decision=?,
                        last_decision_ts=?,
                        reason=?
                    WHERE uid=?
                """, (now, now, close_reason, uid))
                continue

        # ==========================================================
        # PYRAMIDE — VERSION SIMPLE
        # IMPORTANT (INVARIANT REPO):
        # - follower.step NE DOIT PAS bouger sur *_req
        # - step bouge UNIQUEMENT sur *_done via follower_fsm_sync.py
        # ==========================================================
        ok, why, ratio_or_req = _should_pyramide(fr, fr_full, CFG, now)
        if ok:
            ratio_add = float(ratio_or_req)

            f.execute("""
                UPDATE follower
                SET status='pyramide_req',
                    qty_to_add_ratio=?,
                    ratio_to_add=?,
                    req_step=req_step+1,
                    ts_decision=?,
                    last_decision_ts=?,
                    nb_pyramide=nb_pyramide+1,
                    cooldown_pyramide_ts=?,
                    last_pyramide_ts=?,
                    last_pyramide_mfe_atr=?,
                    reason='PYRAMIDE_SIMPLE'
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

            log.info("[PYRAMIDE] uid=%s ratio=%.4f mfe_atr=%.4f nb_pyr->%d", uid, ratio_add, float(fr["mfe_atr"] or 0.0), int(fr["nb_pyramide"] or 0) + 1)
            continue

        # ==========================================================
        # PARTIAL — FILTRE TRADABILITÉ
        # IMPORTANT (INVARIANT REPO):
        # - follower.step NE DOIT PAS bouger sur *_req
        # ==========================================================
        if fr["mfe_atr"] >= CFG["partial_mfe_atr"] and fr["nb_partial"] == 0:

            ratio_cfg = CFG["partial_close_ratio"]
            qty_open = float(fr["qty_open"] or 0.0)
            if qty_open <= 0:
                continue

            min_qty = CFG.get("min_partial_qty", 0.0)
            ratio_min_exec = (min_qty / qty_open) if qty_open > 0 else 999.0

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

            f.execute("""
                UPDATE follower
                SET status='partial_req',
                    qty_to_close_ratio=?,
                    ratio_to_close=?,
                    req_step=req_step+1,
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
