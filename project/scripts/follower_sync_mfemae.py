#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FOLLOWER — SYNC MFE / MAE (CANONIQUE)

Responsabilité UNIQUE :
- lire mfe_mae.db
- projeter mfe_atr / mae_atr dans follower.db
- AUCUNE logique de décision
- AUCUNE écriture ailleurs que follower.db
"""

import sqlite3
import time
from pathlib import Path

# ============================================================
# PATHS
# ============================================================

ROOT = Path("/opt/scalp/project")

DB_FOLLOWER = ROOT / "data/follower.db"
DB_MFEMAE   = ROOT / "data/mfe_mae.db"

# ============================================================
# UTILS
# ============================================================

def conn(db):
    c = sqlite3.connect(str(db), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c

# ============================================================
# API CANONIQUE (IMPORTÉE PAR follower.py)
# ============================================================

def sync_mfemae(f, m):
    """
    Synchronise mfe_atr / mae_atr dans follower
    Matching STRICT par uid (design actuel)
    """

    follower_cols = {r["name"] for r in f.execute("PRAGMA table_info(follower)").fetchall()}

    rows = m.execute("""
        SELECT
            uid,
            mfe,
            mae,
            atr,
            mfe_ts,
            mae_ts,
            ts_updated
        FROM mfe_mae
        WHERE atr IS NOT NULL
          AND atr > 0
    """).fetchall()

    if not rows:
        return

    now = int(time.time() * 1000)

    for r in rows:
        mfe_atr = (r["mfe"] or 0.0) / r["atr"]
        mae_atr = abs(r["mae"] or 0.0) / r["atr"]

        set_parts = ["mfe_atr = ?", "mae_atr = ?"]
        params = [mfe_atr, mae_atr]

        if "mfe_price" in follower_cols:
            set_parts.append("mfe_price = ?")
            params.append(r["mfe"])

        if "mae_price" in follower_cols:
            set_parts.append("mae_price = ?")
            params.append(r["mae"])

        if "atr_signal" in follower_cols:
            set_parts.append("atr_signal = ?")
            params.append(r["atr"])

        if "mfe_ts" in follower_cols:
            set_parts.append("mfe_ts = ?")
            params.append(r["mfe_ts"])

        if "mae_ts" in follower_cols:
            set_parts.append("mae_ts = ?")
            params.append(r["mae_ts"])

        if "ts_updated" in follower_cols:
            set_parts.append("ts_updated = ?")
            params.append(r["ts_updated"] if r["ts_updated"] is not None else now)

        params.append(r["uid"])

        f.execute(
            f"UPDATE follower SET {', '.join(set_parts)} WHERE uid = ?",
            tuple(params),
        )

# ============================================================
# MODE STANDALONE (DEBUG UNIQUEMENT)
# ============================================================

if __name__ == "__main__":
    f = conn(DB_FOLLOWER)
    m = conn(DB_MFEMAE)

    sync_mfemae(f, m)

    f.commit()
    f.close()
    m.close()
