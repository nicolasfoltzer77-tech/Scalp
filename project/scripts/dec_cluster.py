#!/usr/bin/env python3

import sqlite3
import time
from pathlib import Path

ROOT = Path("/opt/scalp/project")
DB = ROOT / "data/dec.db"


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def refresh_cluster_history():

    with conn() as c:

        r = c.execute("""
        SELECT
        strftime('%s','now') AS ts,
        breakout_count,
        avg_energy
        FROM v_signal_cluster
        """).fetchone()

        if not r:
            return 0

        c.execute("""
        INSERT INTO cluster_history
        VALUES (?,?,?)
        """, (r["ts"], r["breakout_count"], r["avg_energy"]))

        c.execute("""
        DELETE FROM cluster_history
        WHERE ts < strftime('%s','now')-300
        """)

        return 1
