#!/usr/bin/env python3
import sqlite3
import time
from pathlib import Path

DB = "/opt/scalp/project/data/closer.db"
Path("/opt/scalp/project/data").mkdir(parents=True, exist_ok=True)

def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS trades_close (
        instId TEXT,
        side TEXT,
        px REAL,
        sz REAL,
        ts_close INTEGER
    )
    """)
    con.commit()

    while True:
        time.sleep(10)

if __name__ == "__main__":
    main()
