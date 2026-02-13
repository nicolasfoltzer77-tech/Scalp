#!/usr/bin/env python3
import sqlite3
import time
import json
from pathlib import Path

DB = "/opt/scalp/project/data/ob.db"
Path("/opt/scalp/project/data").mkdir(parents=True, exist_ok=True)

def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ob_raw (
        instId TEXT,
        ts INTEGER,
        bids TEXT,
        asks TEXT
    )
    """)

    # Placeholder: lecture stdin / socket externe remplacée par boucle neutre
    while True:
        ts = int(time.time() * 1000)
        instId = "SIM"
        bids = json.dumps([[100.0, 1.0]])
        asks = json.dumps([[100.1, 1.0]])

        cur.execute(
            "INSERT INTO ob_raw(instId, ts, bids, asks) VALUES (?,?,?,?)",
            (instId, ts, bids, asks),
        )
        con.commit()
        time.sleep(1)

if __name__ == "__main__":
    main()
