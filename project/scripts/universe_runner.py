#!/usr/bin/env python3
import sqlite3
import time

DB = "/opt/scalp/project/data/u.db"

def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()

    while True:
        rows = cur.execute(
            "SELECT source FROM sources WHERE enabled=1"
        ).fetchall()
        for (src,) in rows:
            print(f"[universe_runner] enabled source: {src}")
        time.sleep(5)

if __name__ == "__main__":
    main()
