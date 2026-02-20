#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import sqlite3
import logging
from pathlib import Path

from exec_from_opener import ingest_from_opener

LOG = "/opt/scalp/project/logs/exec.log"

logging.basicConfig(
    filename=LOG,
    level=logging.INFO,
    format="%(asctime)s EXEC %(levelname)s %(message)s"
)

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
        # 1) ingest opener -> exec
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
                step = r["step"]

                if r["exec_type"] == "pyramide":
                    step += 1

                e.execute("""
                    UPDATE exec
                    SET status='done',
                        step=?,
                        ts_exec=?,
                        done_step=1
                    WHERE exec_id=?
                """, (
                    step,
                    now_ms(),
                    r["exec_id"]
                ))

                log.info(
                    "[EXEC_DONE] uid=%s type=%s step=%s",
                    r["uid"],
                    r["exec_type"],
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
