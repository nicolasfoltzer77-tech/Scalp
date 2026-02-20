#!/usr/bin/env python3
import sqlite3
from pathlib import Path

BASE = Path("/opt/scalp/project/data")

def ro(db):
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True)

print("=== DIAG OPEN -> EXEC ===")

with ro(BASE / "opener.db") as c:
    rows = c.execute(
        "SELECT uid, status FROM opener WHERE status='open_stdby'"
    ).fetchall()
    print(f"[opener] open_stdby rows: {len(rows)}")

with ro(BASE / "exec.db") as c:
    all_exec = c.execute("SELECT uid, status FROM exec").fetchall()
    print(f"[exec] total rows: {len(all_exec)}")

    open_done = [
        (u, s) for (u, s) in all_exec if s == "open_done"
    ]
    print(f"[exec] open_done rows: {len(open_done)}")

print("Expected:")
print("- opener.open_stdby > 0")
print("- exec.open_done should increase")
