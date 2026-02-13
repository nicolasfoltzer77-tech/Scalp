#!/usr/bin/env python3
import sqlite3
import json
import time
from pathlib import Path

DB_IN = "/opt/scalp/project/data/ob.db"
DB_OUT = "/opt/scalp/project/data/ob_feat.db"
Path("/opt/scalp/project/data").mkdir(parents=True, exist_ok=True)

def main():
    con_in = sqlite3.connect(DB_IN)
    con_out = sqlite3.connect(DB_OUT)

    cur_in = con_in.cursor()
    cur_out = con_out.cursor()

    cur_out.execute("""
    CREATE TABLE IF NOT EXISTS ob_feat (
        instId TEXT,
        ts INTEGER,
        bid_px REAL,
        ask_px REAL,
        spread REAL,
        imbalance REAL
    )
    """)

    while True:
        row = cur_in.execute(
            "SELECT instId, ts, bids, asks FROM ob_raw ORDER BY ts DESC LIMIT 1"
        ).fetchone()

        if row:
            instId, ts, bids, asks = row
            bids = json.loads(bids)
            asks = json.loads(asks)

            bid_px = bids[0][0]
            ask_px = asks[0][0]
            spread = ask_px - bid_px
            imbalance = 0.0

            cur_out.execute(
                "INSERT INTO ob_feat VALUES (?,?,?,?,?,?)",
                (instId, ts, bid_px, ask_px, spread, imbalance),
            )
            con_out.commit()

        time.sleep(1)

if __name__ == "__main__":
    main()
