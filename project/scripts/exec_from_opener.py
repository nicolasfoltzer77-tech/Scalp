#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCALP — EXEC FROM OPENER

Responsabilité :
- lire opener.db (read-only)
- ingérer les ordres prêts dans exec.db.exec
- respecter strictement le modèle single-writer

Aucun refactor.
Strictement additif.
"""

import sqlite3
import logging
from pathlib import Path
import time

log = logging.getLogger("EXEC_FROM_OPENER")

ROOT = Path("/opt/scalp/project")

DB_OPENER = ROOT / "data/opener.db"
DB_EXEC   = ROOT / "data/exec.db"


def conn_opener():
    c = sqlite3.connect(f"file:{DB_OPENER}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def conn_exec():
    c = sqlite3.connect(str(DB_EXEC), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c


def ingest_from_opener():
    """
    Copie des ordres opener → exec
    """

    o = conn_opener()
    e = conn_exec()

    try:
        rows = o.execute("""
            SELECT
                uid,
                exec_type,
                step
            FROM opener_exec_ready
        """).fetchall()

        for r in rows:
            uid = r["uid"]
            exec_type = r["exec_type"]
            step = r["step"] or 0

            exists = e.execute("""
                SELECT 1
                FROM exec
                WHERE uid=?
            """, (uid,)).fetchone()

            if exists:
                continue

            e.execute("""
                INSERT INTO exec (
                    uid,
                    exec_type,
                    step,
                    status,
                    ts_create
                ) VALUES (?, ?, ?, 'open', ?)
            """, (
                uid,
                exec_type,
                step,
                int(time.time() * 1000)
            ))

            log.info(
                "[INGEST] uid=%s type=%s step=%s",
                uid,
                exec_type,
                step
            )

        e.commit()

    except Exception:
        log.exception("[ERR] exec_from_opener")
        try:
            e.rollback()
        except Exception:
            pass

    finally:
        o.close()
        e.close()
