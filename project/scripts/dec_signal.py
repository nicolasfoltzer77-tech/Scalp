#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DEC — SIGNAL ENGINE

Maintient l'historique des signaux pour :

• persistence
• half-life
• decay
• liquidity gravity

La logique math est dans les VIEWS SQL.
Ce script ne fait que nourrir signal_history.
"""

import sqlite3
import time
from pathlib import Path

ROOT = Path("/opt/scalp/project")
DB_DEC = ROOT / "data/dec.db"

WINDOW_SEC = 600


def conn():
    c = sqlite3.connect(str(DB_DEC), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c


def now():
    return int(time.time())


def refresh_signal_history():

    ts = now()

    with conn() as c:

        rows = c.execute("""
        SELECT
        instId,
        final_energy
        FROM v_breakout_energy_final
        """).fetchall()

        payload = []

        for r in rows:
            try:
                energy = float(r["final_energy"])
            except Exception:
                continue

            payload.append((r["instId"], ts, energy))

        if payload:
            c.executemany(
                "INSERT INTO signal_history(instId, ts, energy) VALUES (?,?,?)",
                payload
            )

        # purge vieux signaux
        c.execute(
            "DELETE FROM signal_history WHERE ts < ?",
            (ts - WINDOW_SEC,)
        )

        return len(payload)


if __name__ == "__main__":

    n = refresh_signal_history()

    print("signal rows inserted:", n)
