#!/usr/bin/env python3
import sqlite3
from pathlib import Path

DB = "/opt/scalp/project/data/t.db"
Path("/opt/scalp/project/data").mkdir(parents=True, exist_ok=True)

def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    rows = cur.execute(
        "SELECT instId, lastPr, ts_ms FROM ticks ORDER BY ts_ms DESC LIMIT 10"
    ).fetchall()
    for r in rows:
        print(r)
    con.close()

if __name__ == "__main__":
    main()
