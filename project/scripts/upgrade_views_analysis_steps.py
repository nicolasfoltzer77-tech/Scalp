#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCALP — UPGRADE ANALYSIS VIEWS (STEP / EXIT / PERFORMANCE)

RÈGLES :
- AUCUNE modification de données
- AUCUN recalcul métier
- uniquement des VUES SQL
- source : exec.db + recorder.db
"""

import sqlite3
from pathlib import Path

ROOT = Path("/opt/scalp/project")

DB_EXEC = ROOT / "data/exec.db"
DB_REC  = ROOT / "data/recorder.db"

def conn(db):
    c = sqlite3.connect(str(db))
    c.execute("PRAGMA journal_mode=WAL;")
    return c

# ============================================================
# EXEC.DB — ANALYSE PAR STEP / TYPE
# ============================================================

def upgrade_exec_views():
    c = conn(DB_EXEC)

    # --------------------------------------------------------
    # STEP PERFORMANCE
    # --------------------------------------------------------
    c.execute("""
    CREATE VIEW IF NOT EXISTS v_exec_perf_by_step AS
    SELECT
        step,
        COUNT(*)                       AS n,
        AVG(pnl_realized_step)         AS exp,
        SUM(CASE WHEN pnl_realized_step > 0 THEN pnl_realized_step ELSE 0 END)
        / ABS(SUM(CASE WHEN pnl_realized_step < 0 THEN pnl_realized_step ELSE 0 END)) AS pf
    FROM exec
    WHERE exec_type IN ('close','partial')
    GROUP BY step;
    """)

    # --------------------------------------------------------
    # EXIT TYPE PERFORMANCE
    # --------------------------------------------------------
    c.execute("""
    CREATE VIEW IF NOT EXISTS v_exec_perf_by_exit AS
    SELECT
        reason,
        COUNT(*)                       AS n,
        AVG(pnl_realized_step)         AS exp,
        SUM(CASE WHEN pnl_realized_step > 0 THEN pnl_realized_step ELSE 0 END)
        / ABS(SUM(CASE WHEN pnl_realized_step < 0 THEN pnl_realized_step ELSE 0 END)) AS pf
    FROM exec
    WHERE exec_type IN ('close','partial')
    GROUP BY reason;
    """)

    # --------------------------------------------------------
    # STEP × EXIT
    # --------------------------------------------------------
    c.execute("""
    CREATE VIEW IF NOT EXISTS v_exec_perf_step_exit AS
    SELECT
        step,
        reason,
        COUNT(*)                       AS n,
        AVG(pnl_realized_step)         AS exp
    FROM exec
    WHERE exec_type IN ('close','partial')
    GROUP BY step, reason;
    """)

    c.commit()
    c.close()

# ============================================================
# RECORDER.DB — CONTEXTE ASSOCIÉ
# ============================================================

def upgrade_recorder_views():
    c = conn(DB_REC)

    # --------------------------------------------------------
    # PERFORMANCE STEP AVEC CONTEXTE
    # --------------------------------------------------------
    c.execute("""
    CREATE VIEW IF NOT EXISTS v_rec_perf_step_context AS
    SELECT
        r.close_steps          AS step,
        COUNT(*)               AS n,
        AVG(r.pnl_realized)    AS exp,
        AVG(r.mfe_atr)         AS mfe,
        AVG(r.mae_atr)         AS mae,
        SUM(r.golden)          AS golden
    FROM recorder r
    GROUP BY r.close_steps;
    """)

    # --------------------------------------------------------
    # EXIT TYPE AVEC CONTEXTE
    # --------------------------------------------------------
    c.execute("""
    CREATE VIEW IF NOT EXISTS v_rec_perf_exit_context AS
    SELECT
        r.reason_close         AS exit_type,
        COUNT(*)               AS n,
        AVG(r.pnl_realized)    AS exp,
        AVG(r.mfe_atr)         AS mfe,
        AVG(r.mae_atr)         AS mae,
        SUM(r.golden)          AS golden
    FROM recorder r
    GROUP BY r.reason_close;
    """)

    c.commit()
    c.close()

# ============================================================
# MAIN
# ============================================================

def main():
    upgrade_exec_views()
    upgrade_recorder_views()
    print("✅ Analysis views upgraded (STEP / EXIT / PERFORMANCE)")

if __name__ == "__main__":
    main()

