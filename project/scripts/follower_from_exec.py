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

    for ex in e.execute("""
        SELECT uid, exec_type, step
        FROM exec
        WHERE status='done'
    """):

        uid  = ex["uid"]
        etyp = ex["exec_type"]
        step = int(ex["step"] or 0)

        fr = f.execute("SELECT status, step FROM follower WHERE uid=?", (uid,)).fetchone()
        if not fr:
            continue

        # =====================================================
        # OPEN terminé → follower passe follow
        # =====================================================
        if etyp in ("open","pyramide"):
            f.execute("""
                UPDATE follower
                SET status='follow',
                    step=?,
                    ts_updated=?
                WHERE uid=?
            """,(step, now_ms(), uid))

        # =====================================================
        # PARTIAL exécuté → demander prochaine étape à GEST
        # =====================================================
        elif etyp == "partial":
            f.execute("""
                UPDATE follower
                SET status='follow',
                    step=?,
                    ts_updated=?
                WHERE uid=?
            """,(step, now_ms(), uid))

        # =====================================================
        # CLOSE exécuté → fin de vie
        # =====================================================
        elif etyp == "close":
            f.execute("""
                UPDATE follower
                SET status='follow',
                    step=?,
                    ts_updated=?
                WHERE uid=?
            """,(step, now_ms(), uid))

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

