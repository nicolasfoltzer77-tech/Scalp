#!/usr/bin/env python3
import sqlite3, time

DB_H="/opt/scalp/project/data/x_history.db"

def latest_H():
    con=sqlite3.connect(DB_H)
    row=con.execute("SELECT score_H FROM v_H_latest").fetchone()
    con.close()
    return float(row[0]) if row and row[0] else 0.0

def run():
    h=latest_H()
    print(f"[H] score_H={h:.3f}")

if __name__=="__main__":
    run()

