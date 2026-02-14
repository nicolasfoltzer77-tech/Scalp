#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FOLLOWER — ARMEMENT DES NIVEAUX
SL_BE / SL_TRAIL / TP_DYN

FIXES (non-breaking):
1) sl_be/sl_trail peuvent être stockés avec DEFAULT 0.0 -> 0.0 = "NON ARMÉ".
2) Certains environnements n'ont pas (ou pas à jour) la table gest suivie ici.
   -> fallback: armer depuis la table follower directement (status='follow').

Objectif: BE/TRAIL doivent s'armer dès que MFE_ATR dépasse les seuils, sans dépendance fragile.
"""

def _is_unarmed(x):
    try:
        return (x is None) or (float(x) <= 0.0)
    except Exception:
        return True

def _get_entry(row):
    # best-effort across schemas
    for k in ("entry", "entry_price", "entry_px"):
        if k in row.keys() and row[k] is not None:
            try:
                v = float(row[k])
                if v != 0.0:
                    return v
            except Exception:
                pass
    return None

def _get_side(row):
    for k in ("side",):
        if k in row.keys() and row[k] is not None:
            return str(row[k])
    return None

def _get_atr_signal(row):
    for k in ("atr_signal", "atr", "atr_ref"):
        if k in row.keys() and row[k] is not None:
            try:
                v = float(row[k])
                if v > 0:
                    return v
            except Exception:
                pass
    return None

def _arm_one(f, uid, side, entry, mfe_atr, fr, CFG):
    sl_be    = fr["sl_be"]    if "sl_be" in fr.keys()    else None
    sl_trail = fr["sl_trail"] if "sl_trail" in fr.keys() else None
    tp_dyn   = fr["tp_dyn"]   if "tp_dyn" in fr.keys()   else None

    atr_sig = _get_atr_signal(fr)
    if atr_sig is None:
        atr_sig = 0.0

    # --- SL BE ---
    if _is_unarmed(sl_be) and mfe_atr >= float(CFG["sl_be_atr_trigger"]):
        if entry is not None:
            sl_be = float(entry)

    # --- SL TRAIL ---
    if _is_unarmed(sl_trail) and mfe_atr >= float(CFG["sl_trail_atr_trigger"]):
        off = float(CFG["sl_trail_offset_atr"]) * float(atr_sig)
        if entry is not None:
            if side == "sell":
                sl_trail = float(entry) - off
            else:
                sl_trail = float(entry) + off

    # --- TP DYN ---
    if (tp_dyn is None or (isinstance(tp_dyn, (int, float)) and float(tp_dyn) == 0.0)) and mfe_atr >= float(CFG["tp_dyn_atr_trigger"]):
        mul = float(CFG["tp_dyn_atr_mult"]) * float(atr_sig)
        if entry is not None:
            if side == "sell":
                tp_dyn = float(entry) - mul
            else:
                tp_dyn = float(entry) + mul

    f.execute(
        "UPDATE follower SET sl_be=?, sl_trail=?, tp_dyn=? WHERE uid=?",
        (sl_be, sl_trail, tp_dyn, uid)
    )

def arm_levels(f, g, CFG):
    """
    f: sqlite conn follower.db (writer)
    g: sqlite conn gest.db (read-only) - may be empty / not in sync
    """

    # ---------------------------------------------------------
    # PRIMARY PATH: from gest (when available and in sync)
    # ---------------------------------------------------------
    did_any = False
    try:
        for r in g.execute("""
            SELECT uid, side, entry
            FROM gest
            WHERE status='follow'
        """):
            uid = r["uid"]
            fr = f.execute("SELECT * FROM follower WHERE uid=?", (uid,)).fetchone()
            if not fr:
                continue

            mfe_atr = fr["mfe_atr"] if "mfe_atr" in fr.keys() else None
            if mfe_atr is None:
                continue

            entry = None
            try:
                entry = float(r["entry"]) if r["entry"] is not None else None
            except Exception:
                entry = None

            side = str(r["side"]) if r["side"] is not None else _get_side(fr)
            if side is None:
                continue

            _arm_one(f, uid, side, entry, float(mfe_atr), fr, CFG)
            did_any = True
    except Exception:
        # swallow and fallback
        did_any = False

    # ---------------------------------------------------------
    # FALLBACK PATH: from follower itself (robust)
    # ---------------------------------------------------------
    if not did_any:
        for fr in f.execute("""
            SELECT *
            FROM follower
            WHERE status='follow'
        """):
            uid = fr["uid"]

            mfe_atr = fr["mfe_atr"] if "mfe_atr" in fr.keys() else None
            if mfe_atr is None:
                continue

            entry = _get_entry(fr)
            side  = _get_side(fr)
            if side is None:
                continue

            _arm_one(f, uid, side, entry, float(mfe_atr), fr, CFG)
