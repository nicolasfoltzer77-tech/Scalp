#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DEC — Extended range metrics

Compute:
- range50
- range100
- range200
- compression score
- volatility score
"""

import sqlite3
import time
from pathlib import Path

ROOT = Path("/opt/scalp/project")

DB_OB  = ROOT / "data/ob.db"
DB_DEC = ROOT / "data/dec.db"


def conn(path):
    c = sqlite3.connect(str(path), timeout=10)
    c.row_factory = sqlite3.Row
    return c


def compute_range(rows, n):

    if len(rows) < n:
        return None, None

    window = rows[-n:]

    high = max(r["h"] for r in window)
    low  = min(r["l"] for r in window)

    return high, low


def refresh_snap_range_ext():

    ts = int(time.time()*1000)

    with conn(DB_OB) as ob:

        insts = ob.execute(
            "SELECT DISTINCT instId FROM ohlcv_1m"
        ).fetchall()

        payload = []

        for inst in insts:

            instId = inst["instId"]

            rows = ob.execute(
                """
                SELECT h,l,c
                FROM ohlcv_1m
                WHERE instId=?
                ORDER BY ts
                """,
                (instId,)
            ).fetchall()

            if len(rows) < 200:
                continue

            r50  = compute_range(rows,50)
            r100 = compute_range(rows,100)
            r200 = compute_range(rows,200)

            if not r50 or not r100 or not r200:
                continue

            high50,low50   = r50
            high100,low100 = r100
            high200,low200 = r200

            range50  = high50-low50
            range100 = high100-low100
            range200 = high200-low200

            compression = range50 / range200 if range200 else 0
            volatility  = range100 / range200 if range200 else 0

            payload.append(
                (
                    instId,
                    high50,low50,
                    high100,low100,
                    high200,low200,
                    compression,
                    volatility,
                    ts
                )
            )

    with conn(DB_DEC) as dec:

        dec.execute("""
        CREATE TABLE IF NOT EXISTS snap_range_ext(
            instId TEXT PRIMARY KEY,
            high50 REAL,
            low50 REAL,
            high100 REAL,
            low100 REAL,
            high200 REAL,
            low200 REAL,
            compression REAL,
            volatility REAL,
            ts INTEGER
        )
        """)

        dec.executemany("""
        INSERT INTO snap_range_ext
        VALUES (?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(instId) DO UPDATE SET
        high50=excluded.high50,
        low50=excluded.low50,
        high100=excluded.high100,
        low100=excluded.low100,
        high200=excluded.high200,
        low200=excluded.low200,
        compression=excluded.compression,
        volatility=excluded.volatility,
        ts=excluded.ts
        """, payload)

    return len(payload)


if __name__ == "__main__":
    n = refresh_snap_range_ext()
    print("snap_range_ext rows:", n)

