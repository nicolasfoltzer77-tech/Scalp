#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import sqlite3
import logging
from pathlib import Path

from exec_from_opener import ingest_from_opener

log = logging.getLogger("EXEC")

ROOT = Path("/opt/scalp/project")
DB_EXEC = ROOT / "data/exec.db"


def conn():
    c = sqlite3.connect(str(DB_EXEC), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c


def now_ms():
    return int(time.time() * 1000)


def main():
    log.info("[START] exec")

    while True:
        # --------------------------------------------------
        # NOUVEAU : ingestion opener → exec
        # --------------------------------------------------
        try:
            ingest_from_opener()
        except Exception:
            log.exception("[ERR] ingest_from_opener")

        e = conn()

        try:
            rows = e.execute("""
                SELECT *
                FROM exec
                WHERE status='open'
            """).fetchall()

            for r in rows:
                uid = r["uid"]
                exec_type = r["exec_type"]
                step = r["step"] or 0

                # --------------------------------------------------
                # exécution réelle (exchange / simulateur)
                # --------------------------------------------------

                # ==================================================
                # EXISTANT — inchangé
                # ==================================================
                if exec_type == "pyramide":
                    step = step + 1
                # ==================================================

                e.execute("""
                    UPDATE exec
                    SET status='done',
                        step=?,
                        ts_done=?
                    WHERE id=?
                """, (
                    step,
                    now_ms(),
                    r["id"]
                ))

                log.info(
                    "[EXEC_DONE] uid=%s type=%s step=%s",
                    uid,
                    exec_type,
                    step
                )

            e.commit()

        except Exception:
            log.exception("[ERR] exec loop")
            try:
                e.rollback()
            except Exception:
                pass

        finally:
            e.close()

        time.sleep(0.2)


if __name__ == "__main__":
    main()
