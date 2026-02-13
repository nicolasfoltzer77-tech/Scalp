#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import logging
import sqlite3
import yaml
from pathlib import Path

from follower_ingest import ingest_open_done
from follower_sync_mfemae import sync_mfemae
from follower_fsm_sync import sync_fsm_status
from follower_timeout import apply_timeouts
from follower_decide import decide_core
from follower_purge_closed import purge_closed

ROOT = Path("/opt/scalp/project")

DB_FOLLOWER = ROOT / "data/follower.db"
DB_GEST     = ROOT / "data/gest.db"
DB_EXEC     = ROOT / "data/exec.db"
DB_MFEMAE   = ROOT / "data/mfe_mae.db"   # ✅ CORRECTION NOM FICHIER
DB_TICKS    = ROOT / "data/ticks.db"

CFG = yaml.safe_load(
    open(ROOT / "conf/follower.yaml", "r")
)["follower"]

log = logging.getLogger("FOLLOWER")
logging.basicConfig(level=logging.INFO)

def conn(db):
    c = sqlite3.connect(str(db), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=10000;")
    return c

def now_ms():
    return int(time.time() * 1000)

def main():
    log.info("[START] follower orchestrator")

    while True:
        now = now_ms()

        f = conn(DB_FOLLOWER)
        g = conn(DB_GEST)
        e = conn(DB_EXEC)
        m = conn(DB_MFEMAE)
        t = conn(DB_TICKS)

        try:
            ingest_open_done(g, f, now)
            sync_mfemae(f, m)
            sync_fsm_status(g, f, now)

            rows_exec = e.execute("""
                SELECT uid,
                       qty_open,
                       avg_price_open,
                       last_exec_type,
                       last_step,
                       last_price_exec,
                       last_ts_exec
                FROM v_exec_position
            """).fetchall()

            for r_exec in rows_exec:
                f.execute("""
                    UPDATE follower
                    SET qty_open=?,
                        avg_price_open=?,
                        last_exec_type=?,
                        last_step=?,
                        last_price_exec=?,
                        last_ts_exec=?
                    WHERE uid=?
                """, (
                    r_exec["qty_open"],
                    r_exec["avg_price_open"],
                    r_exec["last_exec_type"],
                    r_exec["last_step"],
                    r_exec["last_price_exec"],
                    r_exec["last_ts_exec"],
                    r_exec["uid"]
                ))

            rows = f.execute("""
                SELECT *
                FROM v_follower_state
                WHERE status='follow'
            """).fetchall()

            for r in rows:
                apply_timeouts(
                    f=f,
                    fr=r,
                    qty_open=r["qty_ratio"] or 1.0,
                    age_s=r["age_s"],
                    CFG=CFG,
                    now=now
                )

            decide_core(f=f, CFG=CFG, now=now)
            purge_closed(g, f, now)

            f.commit()

        except Exception:
            log.exception("[ERR] follower loop")

        finally:
            f.close()
            g.close()
            e.close()
            m.close()
            t.close()

        time.sleep(0.5)

if __name__ == "__main__":
    main()

