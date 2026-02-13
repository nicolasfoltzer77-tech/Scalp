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

    rows = m.execute("""
        SELECT
            uid,
            mfe,
            mae,
            atr
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

        f.execute("""
            UPDATE follower
            SET
                mfe_atr = ?,
                mae_atr = ?,
                ts_updated = ?
            WHERE uid = ?
        """, (
            mfe_atr,
            mae_atr,
            now,
            r["uid"]
        ))

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

