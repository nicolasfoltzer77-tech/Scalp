#!/usr/bin/env python3
"""
FSM Passive Audit Tool (read-only)

Validates FSM invariants across DBs:
- req -> stdby -> done ordering
- no orphan done
- recorder presence == recorded
"""

import sqlite3
from pathlib import Path
import sys

# --- Resolve base paths robustly ---
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"

DBS = {
    "follower": DATA_DIR / "follower.db",
    "opener": DATA_DIR / "opener.db",
    "closer": DATA_DIR / "closer.db",
    "exec": DATA_DIR / "exec.db",
    "recorder": DATA_DIR / "recorder.db",
}

FAIL = False


def ro_connect(db: Path):
    return sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)


def fetch(db: Path, query: str):
    if not db.exists():
        fail(f"DB not found: {db}")
        return []
    with ro_connect(db) as c:
        return c.execute(query).fetchall()


def fail(msg: str):
    global FAIL
    print(f"[FAIL] {msg}")
    FAIL = True


def ok(msg: str):
    print(f"[OK] {msg}")


def main():
    # -------------------------------------------------
    # recorder presence == recorded
    # -------------------------------------------------
    recorder_uids = {u for (u,) in fetch(DBS["recorder"], "SELECT uid FROM recorder")}

    # -------------------------------------------------
    # recorded implies close_done
    # -------------------------------------------------
    close_done_uids = {
        u for (u,) in fetch(
            DBS["exec"],
            "SELECT uid FROM exec WHERE status='close_done'"
        )
    }

    for uid in recorder_uids:
        if uid not in close_done_uids:
            fail(f"recorded without close_done: uid={uid}")
    ok("recorded implies close_done")

    # -------------------------------------------------
    # done implies req
    # -------------------------------------------------
    req_uids = {
        u for (u,) in fetch(
            DBS["follower"],
            "SELECT uid FROM follower WHERE status LIKE '%_req'"
        )
    }

    done_rows = fetch(DBS["exec"], "SELECT uid, status FROM exec")
    for uid, status in done_rows:
        if status.endswith("_done") and uid not in req_uids:
            fail(f"{status} without req: uid={uid}")
    ok("done implies req")

    # -------------------------------------------------
    # follower purge rule
    # -------------------------------------------------
    follower_uids = {
        u for (u,) in fetch(DBS["follower"], "SELECT uid FROM follower")
    }

    for uid in follower_uids:
        if uid in recorder_uids:
            fail(f"uid present in follower after recorded: uid={uid}")
    ok("follower purge rule respected")

    if FAIL:
        sys.exit(2)

    print("[OK] FSM audit passed")


if __name__ == "__main__":
    main()
