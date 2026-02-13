#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCALP — PIPELINE MONITOR SNAPSHOT (Δ 5 MIN)

- exécution à la demande
- aucune tâche persistante
- 1 writer : monitor.db
- snapshots horodatés
- affichage delta vs T-5min
"""

import sqlite3
import time
from pathlib import Path

ROOT = Path("/opt/scalp/project")

DB_MARKET  = ROOT / "data/market.db"
DB_DEC     = ROOT / "data/dec.db"
DB_TRIG    = ROOT / "data/triggers.db"
DB_MON     = ROOT / "data/monitor.db"

NOW_MS = int(time.time() * 1000)
DELTA_MS = 5 * 60 * 1000


# -------------------------------------------------------------------
# DB UTILS
# -------------------------------------------------------------------

def conn(p):
    c = sqlite3.connect(str(p), timeout=10)
    c.row_factory = sqlite3.Row
    return c

def scalar(db, sql):
    c = conn(db)
    r = c.execute(sql).fetchone()
    c.close()
    return int(list(r)[0]) if r and list(r)[0] is not None else 0


# -------------------------------------------------------------------
# SNAPSHOT COUNTS
# -------------------------------------------------------------------

def collect_counts():
    return {
        "universe": scalar(DB_MARKET, "SELECT COUNT(*) FROM v_market_latest"),
        "market_ok": scalar(
            DB_MARKET,
            "SELECT COUNT(*) FROM v_market_latest WHERE spread_ok=1 AND liquidity_ok=1"
        ),
        "ctx_ok": scalar(
            DB_DEC,
            "SELECT COUNT(*) FROM snap_ctx WHERE ctx_ok=1"
        ),
        "dec_tradable": scalar(
            DB_DEC,
            "SELECT COUNT(*) FROM snap_ctx WHERE ctx_ok=1 AND side IS NOT NULL"
        ),
        "armed": scalar(
            DB_TRIG,
            "SELECT COUNT(*) FROM triggers WHERE status='armed'"
        ),
        "fired": scalar(
            DB_TRIG,
            "SELECT COUNT(*) FROM triggers WHERE status='fired'"
        ),
    }


# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------

def main():
    c = conn(DB_MON)

    # table snapshot
    c.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_snapshot (
            ts_ms INTEGER PRIMARY KEY,
            universe INTEGER,
            market_ok INTEGER,
            ctx_ok INTEGER,
            dec_tradable INTEGER,
            armed INTEGER,
            fired INTEGER
        )
    """)

    counts = collect_counts()

    # insert snapshot
    c.execute("""
        INSERT INTO pipeline_snapshot
        (ts_ms, universe, market_ok, ctx_ok, dec_tradable, armed, fired)
        VALUES (?,?,?,?,?,?,?)
    """, (
        NOW_MS,
        counts["universe"],
        counts["market_ok"],
        counts["ctx_ok"],
        counts["dec_tradable"],
        counts["armed"],
        counts["fired"]
    ))
    c.commit()

    # fetch T-5min snapshot
    prev = c.execute("""
        SELECT *
        FROM pipeline_snapshot
        WHERE ts_ms <= ?
        ORDER BY ts_ms DESC
        LIMIT 1
    """, (NOW_MS - DELTA_MS,)).fetchone()

    c.close()

    def delta(k):
        if not prev:
            return " N/A"
        d = counts[k] - prev[k]
        return f"{d:+4d}"

    # -------------------------------------------------------------------
    # DISPLAY
    # -------------------------------------------------------------------

    print("\nPIPELINE SNAPSHOT (Δ 5 MIN)")
    print("=" * 42)
    print(f"Universe (market) : {counts['universe']:4d}")
    print(f"Market OK         : {counts['market_ok']:4d} ({delta('market_ok')})")
    print(f"CTX OK            : {counts['ctx_ok']:4d} ({delta('ctx_ok')})")
    print(f"DEC tradable      : {counts['dec_tradable']:4d} ({delta('dec_tradable')})")
    print(f"ARMED             : {counts['armed']:4d} ({delta('armed')})")
    print(f"FIRED             : {counts['fired']:4d} ({delta('fired')})")
    print("=" * 42)


if __name__ == "__main__":
    main()

