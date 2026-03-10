#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DEC — SIGNAL HISTORY WRITER
Alimente signal_history depuis breakout_energy
"""

import sqlite3
from pathlib import Path

ROOT = Path("/opt/scalp/project")
DB_DEC = ROOT / "data/dec.db"


def conn():
    c = sqlite3.connect(str(DB_DEC), timeout=5)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    return c


def refresh_signal_history():

    with conn() as c:

        rows = c.execute("""
        SELECT
            instId,
            breakout_energy
        FROM v_breakout_energy_final
        """).fetchall()

        if not rows:
            return 0

        c.executemany("""
        INSERT INTO signal_history (
            instId,
            energy,
            ts
        )
        VALUES (
            ?,
            ?,
            strftime('%s','now')
        )
        """, [
            (r["instId"], r["breakout_energy"])
            for r in rows
        ])

        c.commit()

        return len(rows)


if __name__ == "__main__":
    print(refresh_signal_history())
