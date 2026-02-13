#!/usr/bin/env python3
import sqlite3
import time
from pathlib import Path

DB = "/opt/scalp/project/data/t.db"
Path("/opt/scalp/project/data").mkdir(parents=True, exist_ok=True)

def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ticks (
        instId TEXT,
        lastPr REAL,
        ts_ms INTEGER
    )
    """)

    while True:
        ts = int(time.time() * 1000)
        cur.execute(
            "INSERT INTO ticks(instId, lastPr, ts_ms) VALUES (?,?,?)",
            ("SIM", 100.0, ts),
        )
        con.commit()
        time.sleep(1)

if __name__ == "__main__":
    main()
