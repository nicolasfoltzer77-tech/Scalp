#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FOLLOWER — ne doit JAMAIS produire *_stdby
Rôle : transformer les événements exec en intentions FSM pour GEST.

Règle système :
- *_stdby est STRICTEMENT réservé à opener / closer.
- follower ne produit que : follow | partial_req | close_req | pyramide_req
"""

import sqlite3
import time
import logging
from pathlib import Path

ROOT = Path("/opt/scalp/project")

DB_EXEC     = ROOT / "data/exec.db"
DB_FOLLOWER = ROOT / "data/follower.db"
DB_GEST     = ROOT / "data/gest.db"

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s FOLLOWER %(levelname)s %(message)s")
log = logging.getLogger("FOLLOWER")

def conn(db):
    c = sqlite3.connect(str(db), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c

def now_ms(): return int(time.time()*1000)

# ============================================================
# SANITIZE HARD RULE
# ============================================================

def sanitize_forbidden_states(f):
    f.execute("""
        UPDATE follower
        SET status='follow'
        WHERE status LIKE '%_stdby'
    """)

# ============================================================
# EXEC → FOLLOWER
# ============================================================

def process_exec():
    e = conn(DB_EXEC)
    f = conn(DB_FOLLOWER)
    g = conn(DB_GEST)

    sanitize_forbidden_states(f)

    # IMPORTANT:
    # Plusieurs lignes `exec(done)` existent par uid (open + pyramides + partials).
    # Une itération brute peut réécrire un step plus ancien selon l'ordre de scan
    # SQLite. On matérialise donc le step terminal par uid (= max step done).
    done_rows = e.execute("""
        SELECT
            uid,
            MAX(COALESCE(done_step, step)) AS max_done_step
        FROM exec
        WHERE status='done'
        GROUP BY uid
    """).fetchall()

    for ex in done_rows:

        uid  = ex["uid"]
        step = int(ex["max_done_step"] or 0)

        fr = f.execute("SELECT status, step FROM follower WHERE uid=?", (uid,)).fetchone()
        if not fr:
            continue

        # Ne jamais faire régresser follower.step (sécurité anti-race).
        fr_step = int(fr["step"] or 0)
        if step < fr_step:
            continue

        f.execute("""
            UPDATE follower
            SET status='follow',
                step=?,
                ts_updated=?
            WHERE uid=?
        """, (step, now_ms(), uid))

    f.commit()
    e.close(); f.close(); g.close()

# ============================================================

def main():
    while True:
        try:
            process_exec()
        except Exception as e:
            log.exception(e)
        time.sleep(0.25)

if __name__ == "__main__":
    main()
