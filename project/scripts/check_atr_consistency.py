#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CHECK ATR CONSISTENCY

OBJECTIF :
- Vérifier que l'ATR stocké (gest.atr_signal) est cohérent
- Vérifier que mfe/mae sont bien des PRIX (et non des ATR)
- Calculer mfe_atr / mae_atr réels pour comparaison humaine

AUCUNE ÉCRITURE
READ-ONLY
"""

import sqlite3
from pathlib import Path

ROOT = Path("/opt/scalp/project")

DB_GEST     = ROOT / "data/gest.db"
DB_FOLLOWER = ROOT / "data/follower.db"

def conn(db):
    c = sqlite3.connect(str(db))
    c.row_factory = sqlite3.Row
    return c

g = conn(DB_GEST)
f = conn(DB_FOLLOWER)

print(
    f"{'INST':<12} "
    f"{'ATR':>8} "
    f"{'MFE_P':>8} {'MAE_P':>8} "
    f"{'MFE_ATR':>8} {'MAE_ATR':>8}"
)
print("=" * 70)

for r in f.execute("""
    SELECT
        f.uid,
        f.mfe_price,
        f.mae_price,
        g.instId,
        g.atr_signal
    FROM follower f
    JOIN gest g USING(uid)
    ORDER BY g.ts_open DESC
    LIMIT 20
"""):
    atr = float(r["atr_signal"] or 0)
    mfe_p = float(r["mfe_price"] or 0)
    mae_p = abs(float(r["mae_price"] or 0))

    mfe_atr = mfe_p / atr if atr > 0 else 0
    mae_atr = mae_p / atr if atr > 0 else 0

    print(
        f"{r['instId']:<12} "
        f"{atr:>8.4f} "
        f"{mfe_p:>8.4f} {mae_p:>8.4f} "
        f"{mfe_atr:>8.2f} {mae_atr:>8.2f}"
    )

g.close()
f.close()

