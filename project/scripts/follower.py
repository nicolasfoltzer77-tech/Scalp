#!/usr/bin/env python3
import time
import sqlite3
from pathlib import Path
from fsm import FSM, State

DB = "/opt/scalp/project/data/recorder.db"
Path("/opt/scalp/project/data").mkdir(parents=True, exist_ok=True)

def main():
    fsm = FSM()
    con = sqlite3.connect(DB)
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS trades_record (
        instId TEXT,
        side TEXT,
        px REAL,
        sz REAL,
        ts_record INTEGER
    )
    """)
    con.commit()

    while True:
        state = fsm.on_tick()
        if state == State.OPEN:
            cur.execute(
                "INSERT INTO trades_record VALUES (?,?,?,?,?)",
                ("SIM", "BUY", 100.0, 1.0, int(time.time()*1000))
            )
            con.commit()
        time.sleep(1)

if __name__ == "__main__":
    main()
