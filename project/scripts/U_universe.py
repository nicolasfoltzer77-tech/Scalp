#!/usr/bin/env python3
import sqlite3

DB = "/opt/scalp/project/data/u.db"

def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()

    rows = cur.execute(
        "SELECT source, enabled FROM sources ORDER BY source"
    ).fetchall()

    for r in rows:
        print(r)

    con.close()

if __name__ == "__main__":
    main()
