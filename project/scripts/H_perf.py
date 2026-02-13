#!/usr/bin/env python3
import sqlite3, time, statistics, logging, sys
from pathlib import Path

LOG = "/opt/scalp/project/logs/H_perf.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG), logging.StreamHandler(sys.stdout)]
)

DB_CLOSED = "/opt/scalp/project/data/x_closed.db"
DB_H = "/opt/scalp/project/data/h.db"

def connect_db(path):
    con = sqlite3.connect(path, timeout=30, isolation_level=None)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    con.execute("PRAGMA busy_timeout=5000;")
    return con

def ensure_closed_schema():
    con = connect_db(DB_CLOSED)
    con.execute("""
        CREATE TABLE IF NOT EXISTS positions_closed(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instId TEXT, side TEXT, entry REAL, exit REAL,
            sl REAL, tp REAL, pnl REAL, reason TEXT,
            ts_open INTEGER, ts_close INTEGER
        )
    """)
    con.close()

def migrate_h():
    con = connect_db(DB_H)
    con.execute("""
        CREATE TABLE IF NOT EXISTS score_H(
            instId TEXT PRIMARY KEY,
            avg_pnl REAL,
            winrate REAL,
            trades INTEGER,
            last_update INTEGER
        )
    """)
    con.close()

def compute_score():
    ensure_closed_schema()
    con_c = connect_db(DB_CLOSED)
    rows = con_c.execute("SELECT instId, pnl FROM positions_closed").fetchall()
    con_c.close()
    if not rows:
        logging.info("Aucun trade clos, pas de calcul.")
        return
    data = {}
    for inst,pnl in rows:
        data.setdefault(inst,[]).append(pnl)
    con_h = connect_db(DB_H)
    for inst,vals in data.items():
        avg = statistics.mean(vals)
        winrate = sum(1 for v in vals if v>0)/len(vals)
        con_h.execute("""
            INSERT OR REPLACE INTO score_H(instId,avg_pnl,winrate,trades,last_update)
            VALUES(?,?,?,?,?)
        """,(inst,avg,winrate,len(vals),int(time.time()*1000)))
    con_h.close()
    logging.info(f"Scores H mis à jour pour {len(data)} instruments.")

def main(argv):
    migrate_h()
    compute_score()

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

