#!/usr/bin/env python3
import time
import sqlite3
import pandas as pd

DB = "/opt/scalp/project/data/ob_feat.db"

def loop():
    while True:
        con = sqlite3.connect(DB)
        df = pd.read_sql_query(
            """
            SELECT instId, ts, bid_px, ask_px, spread, imbalance
            FROM ob_feat
            ORDER BY ts DESC
            LIMIT 50
            """,
            con,
        )
        print(df.head(5))
        con.close()
        time.sleep(2)

if __name__ == "__main__":
    loop()
