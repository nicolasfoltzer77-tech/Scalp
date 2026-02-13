#!/usr/bin/env python3
import sqlite3
import pandas as pd

DB = "/opt/scalp/project/data/recorder.db"

def main():
    con = sqlite3.connect(DB)
    df = pd.read_sql_query(
        """
        SELECT instId, side, px, sz, ts_record
        FROM trades_record
        ORDER BY ts_record DESC
        LIMIT 100
        """,
        con,
    )
    print(df.tail(10))
    con.close()

if __name__ == "__main__":
    main()
