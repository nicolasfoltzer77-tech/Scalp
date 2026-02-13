#!/usr/bin/env python3
import sqlite3
import pandas as pd

DB = "/opt/scalp/project/data/ob_feat.db"

def main():
    con = sqlite3.connect(DB)
    df = pd.read_sql_query(
        """
        SELECT instId, ts, bid_px, ask_px, spread, imbalance
        FROM ob_feat
        ORDER BY ts DESC
        LIMIT 500
        """,
        con,
    )
    print(df.head())
    con.close()

if __name__ == "__main__":
    main()
